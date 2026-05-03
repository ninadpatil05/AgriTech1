import os
import random
import shutil
from pathlib import Path


def copy_split(src_root: Path, out_root: Path, val_ratio: float = 0.2, seed: int = 42) -> None:
    random.seed(seed)
    train_root = out_root / "train"
    val_root = out_root / "validation"
    train_root.mkdir(parents=True, exist_ok=True)
    val_root.mkdir(parents=True, exist_ok=True)

    class_dirs = [d for d in src_root.iterdir() if d.is_dir()]
    if not class_dirs:
        raise RuntimeError(f"No class directories found in {src_root}")

    for class_dir in class_dirs:
        images = [p for p in class_dir.iterdir() if p.is_file()]
        if not images:
            continue
        random.shuffle(images)
        split_idx = max(1, int(len(images) * (1 - val_ratio)))
        train_files = images[:split_idx]
        val_files = images[split_idx:]

        dst_train = train_root / class_dir.name
        dst_val = val_root / class_dir.name
        dst_train.mkdir(parents=True, exist_ok=True)
        dst_val.mkdir(parents=True, exist_ok=True)

        for src in train_files:
            shutil.copy2(src, dst_train / src.name)
        for src in val_files:
            shutil.copy2(src, dst_val / src.name)

        print(
            f"{class_dir.name}: total={len(images)} train={len(train_files)} val={len(val_files)}"
        )


def main():
    src = Path(os.environ.get("PLANTVILLAGE_COLOR_DIR", r"D:\CROP_DEC\plantvillage dataset\color"))
    out = Path(os.environ.get("AGRITECH_DISEASE_SPLIT_DIR", r"D:\CROP_DEC\agritech_prepared\disease"))
    val_ratio = float(os.environ.get("AGRITECH_VAL_RATIO", "0.2"))
    copy_split(src, out, val_ratio=val_ratio)
    print(f"\nPrepared dataset at: {out}")
    print(f"Train: {out / 'train'}")
    print(f"Validation: {out / 'validation'}")


if __name__ == "__main__":
    main()
