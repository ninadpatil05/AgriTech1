# AgriTech — Smart Crop Detective

## Configuration

Copy `.env` (see repo root) and adjust:

- `MODEL_PATH` — directory for `.h5` weights (default `models/`; use `.` to load from the project root instead)
- `DB_PATH` — SQLite database file (default `agritech.db`)
- `SECRET_KEY` / `JWT_SECRET` — use strong values in production
- `FLASK_DEBUG` — set `false` in production

## Disease detection models

The Flask API loads two TensorFlow `.h5` files from `MODEL_PATH` (see `config.py`):

- `plant_validator_model.h5` — binary plant vs. non-plant classifier  
- `crop_disease_model.h5` — disease classifier (classes must match `DISEASE_CLASSES` in `blueprints/detection.py`)

**You must supply a suitable dataset** (for example the [PlantVillage](https://www.kaggle.com/datasets/abdallahalidev/plantvillage-dataset) dataset or your own labeled leaf images), point the path constants at the top of `train_cnn.py` to your train/validation folders (or set the `AGRITECH_*` environment variables), then run training and export:

```bash
pip install -r requirements.txt
python train_cnn.py
```

After `train_cnn.py` finishes, confirm both model files exist under `MODEL_PATH` before starting the server:

```bash
python app.py
```

Without these files, `/api/detect` will respond with an error explaining which weights are missing.

## Authentication

`pip install` pulls in `bcrypt` and `PyJWT`. User accounts are stored in SQLite at `DB_PATH`. Set `SECRET_KEY` / `JWT_SECRET` in production.
