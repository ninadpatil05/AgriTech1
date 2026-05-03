import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.applications import MobileNetV2
import os
import json
from pathlib import Path

# AgriTech — Smart Crop Detective: model output directory (match Flask MODEL_PATH / config)
_ROOT = Path(__file__).resolve().parent
_model_raw = os.environ.get("MODEL_PATH", "models").strip()
MODEL_DIR = Path(_model_raw) if os.path.isabs(_model_raw) else _ROOT / _model_raw.strip("/\\")
MODEL_DIR.mkdir(parents=True, exist_ok=True)
AUTOTUNE = tf.data.AUTOTUNE

# -----------------------------------------------------------------------------
# Dataset paths — replace with your local PlantVillage (or compatible) layout
# after downloading the dataset. Train both models before running the Flask app.
# -----------------------------------------------------------------------------
PLANT_VS_NONPLANT_TRAIN_DIR = os.environ.get(
    "AGRITECH_PLANT_TRAIN", "path/to/plant_vs_nonplant/train"
)
PLANT_VS_NONPLANT_VAL_DIR = os.environ.get(
    "AGRITECH_PLANT_VAL", "path/to/plant_vs_nonplant/validation"
)
DISEASE_TRAIN_DIR = os.environ.get(
    "AGRITECH_DISEASE_TRAIN", "path/to/plantvillage_or_disease_dataset/train"
)
DISEASE_VAL_DIR = os.environ.get(
    "AGRITECH_DISEASE_VAL", "path/to/plantvillage_or_disease_dataset/validation"
)

# Saved model filenames (must match Flask config / blueprints/detection.py)
VALIDATOR_SAVE_PATH = str(MODEL_DIR / "plant_validator_model.h5")
DISEASE_SAVE_PATH = str(MODEL_DIR / "crop_disease_model.h5")
DISEASE_FINETUNED_SAVE_PATH = str(MODEL_DIR / "crop_disease_model_finetuned.h5")
DISEASE_CLASSES_PATH = str(MODEL_DIR / "disease_classes.json")

# Configuration
IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32
VALIDATOR_EPOCHS = int(os.environ.get("AGRITECH_VALIDATOR_EPOCHS", "8"))
DISEASE_EPOCHS = int(os.environ.get("AGRITECH_DISEASE_EPOCHS", "12"))
FINETUNE_EPOCHS = int(os.environ.get("AGRITECH_FINETUNE_EPOCHS", "5"))
EARLY_STOPPING_PATIENCE = int(os.environ.get("AGRITECH_EARLY_STOPPING_PATIENCE", "3"))

data_augmentation = tf.keras.Sequential([
    layers.RandomFlip("horizontal_and_vertical"),
    layers.RandomRotation(0.2),
    layers.RandomZoom(0.2),
    layers.RandomContrast(0.2)
], name="data_augmentation")


def _ensure_dir(path_str, title):
    path = Path(path_str)
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(
            f"{title} not found at '{path_str}'. "
            "Set AGRITECH_* environment variables to your PlantVillage folders."
        )
    return path


def _prepare(ds):
    return ds.cache().prefetch(AUTOTUNE)


def load_binary_datasets():
    train_dir = _ensure_dir(PLANT_VS_NONPLANT_TRAIN_DIR, "Plant-vs-NonPlant train directory")
    val_dir = _ensure_dir(PLANT_VS_NONPLANT_VAL_DIR, "Plant-vs-NonPlant validation directory")
    train_ds = tf.keras.utils.image_dataset_from_directory(
        train_dir,
        labels="inferred",
        label_mode="int",
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        shuffle=True,
        seed=42,
    )
    val_ds = tf.keras.utils.image_dataset_from_directory(
        val_dir,
        labels="inferred",
        label_mode="int",
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )
    class_names = [name.lower() for name in train_ds.class_names]
    if set(class_names) != {"nonplant", "plant"}:
        print(
            "Warning: expected binary classes {'plant', 'nonplant'} but found:",
            train_ds.class_names,
        )
    return _prepare(train_ds), _prepare(val_ds)


def load_disease_datasets():
    train_dir = _ensure_dir(DISEASE_TRAIN_DIR, "Disease train directory")
    val_dir = _ensure_dir(DISEASE_VAL_DIR, "Disease validation directory")
    train_ds = tf.keras.utils.image_dataset_from_directory(
        train_dir,
        labels="inferred",
        label_mode="int",
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        shuffle=True,
        seed=42,
    )
    val_ds = tf.keras.utils.image_dataset_from_directory(
        val_dir,
        labels="inferred",
        label_mode="int",
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )
    return _prepare(train_ds), _prepare(val_ds), train_ds.class_names

def build_binary_validator():
    """Builds a binary classifier (Plant vs. Non-Plant) using Transfer Learning."""
    base_model = MobileNetV2(input_shape=(224, 224, 3), include_top=False, weights='imagenet')
    base_model.trainable = False # Freeze base model initially
    
    model = models.Sequential([
        # Data Augmentation layer as preprocessing step
        data_augmentation,
        layers.Lambda(tf.keras.applications.mobilenet_v2.preprocess_input),
        base_model,
        layers.GlobalAveragePooling2D(),
        layers.Dense(128, activation='relu'),
        layers.Dropout(0.3),
        layers.Dense(1, activation='sigmoid') # Binary output: 0 = Non-Plant, 1 = Plant
    ])
    
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss='binary_crossentropy',
                  metrics=['accuracy'])
    return model

def build_disease_classifier(num_classes):
    """Builds a multi-class disease classifier using Transfer Learning."""
    base_model = MobileNetV2(input_shape=(224, 224, 3), include_top=False, weights='imagenet')
    base_model.trainable = False # Freeze base model initially
    
    model = models.Sequential([
        # Data Augmentation layer as preprocessing step
        data_augmentation,
        layers.Lambda(tf.keras.applications.mobilenet_v2.preprocess_input),
        base_model,
        layers.GlobalAveragePooling2D(),
        layers.Dense(256, activation='relu'),
        layers.Dropout(0.4),
        layers.Dense(num_classes, activation='softmax') # Multi-class output
    ])
    
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss='sparse_categorical_crossentropy',
                  metrics=['accuracy'])
    return model

def unfreeze_and_finetune(model, base_model_layer_name, learning_rate=1e-5):
    """
    Unfreezes the top layers of the base model for fine-tuning.
    """
    # Find the base model layer
    base_model = None
    for layer in model.layers:
        if layer.name == base_model_layer_name or isinstance(layer, tf.keras.Model):
            base_model = layer
            break
            
    if base_model:
        # Unfreeze the base model
        base_model.trainable = True
        
        # Fine-tune from this layer onwards (e.g., unfreeze top 20 layers)
        fine_tune_at = len(base_model.layers) - 20
        
        # Freeze all layers before the `fine_tune_at` layer
        for layer in base_model.layers[:fine_tune_at]:
            layer.trainable = False
            
        print(f"Unfrozen top {len(base_model.layers) - fine_tune_at} layers for fine-tuning.")
    
    # Recompile model with a much lower learning rate
    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    
    # Check if it's a binary or multi-class model based on the output layer
    loss_fn = 'binary_crossentropy' if model.layers[-1].units == 1 else 'sparse_categorical_crossentropy'
    
    model.compile(loss=loss_fn,
                  optimizer=optimizer,
                  metrics=['accuracy'])
    return model

def main():
    print("AgriTech — Smart Crop Detective | Training with PlantVillage-compatible folders")
    print(f"  Plant train/val: {PLANT_VS_NONPLANT_TRAIN_DIR} / {PLANT_VS_NONPLANT_VAL_DIR}")
    print(f"  Disease train/val: {DISEASE_TRAIN_DIR} / {DISEASE_VAL_DIR}")
    print(
        f"  Epochs -> validator: {VALIDATOR_EPOCHS}, disease: {DISEASE_EPOCHS}, "
        f"finetune: {FINETUNE_EPOCHS}"
    )

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=EARLY_STOPPING_PATIENCE,
            restore_best_weights=True,
        )
    ]
    
    print("\n--- Building Plant Validator Model ---")
    try:
        binary_train, binary_val = load_binary_datasets()
        validator = build_binary_validator()
        validator.fit(
            binary_train,
            validation_data=binary_val,
            epochs=VALIDATOR_EPOCHS,
            callbacks=callbacks,
        )
        validator.save(VALIDATOR_SAVE_PATH)
        print(f"Saved {VALIDATOR_SAVE_PATH}")
    except FileNotFoundError as err:
        print(f"Skipping validator training: {err}")
        print("Continuing with disease training only.")
    
    print("\n--- Building Disease Classifier Model ---")
    disease_train, disease_val, class_names = load_disease_datasets()
    print(f"Disease classes ({len(class_names)}): {class_names}")
    disease_model = build_disease_classifier(num_classes=len(class_names))
    disease_model.fit(
        disease_train,
        validation_data=disease_val,
        epochs=DISEASE_EPOCHS,
        callbacks=callbacks,
    )
    disease_model.save(DISEASE_SAVE_PATH)
    print(f"Saved {DISEASE_SAVE_PATH}")
    
    print("\n--- Fine-tuning the Disease Classifier ---")
    print("To improve accuracy, we unfreeze the top layers and fine-tune with a lower learning rate.")
    disease_model_finetuned = unfreeze_and_finetune(disease_model, base_model_layer_name='mobilenetv2_1.00_224')
    disease_model_finetuned.fit(
        disease_train,
        validation_data=disease_val,
        epochs=FINETUNE_EPOCHS,
        callbacks=callbacks,
    )
    disease_model_finetuned.save(DISEASE_FINETUNED_SAVE_PATH)
    print(f"Saved {DISEASE_FINETUNED_SAVE_PATH}")
    disease_model_finetuned.save(DISEASE_SAVE_PATH)
    print(f"Updated Flask weights at {DISEASE_SAVE_PATH} using fine-tuned model.")
    with open(DISEASE_CLASSES_PATH, "w", encoding="utf-8") as f:
        json.dump(class_names, f, ensure_ascii=True, indent=2)
    print(f"Saved disease class labels to {DISEASE_CLASSES_PATH}")

if __name__ == '__main__':
    main()
