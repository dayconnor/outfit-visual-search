import json
import pathlib

import pandas as pd

repo_root = pathlib.Path(__file__).resolve().parents[1]
raw_dir = repo_root/'data'/'raw'
processed_dir = repo_root/'data'/'processed'

train_annotations_path = raw_dir/'instances_attributes_train2020.json'
val_annotations_path = raw_dir/'instances_attributes_val2020.json'
train_image_dir = raw_dir/'train'

part_supercategories = {'garment parts', 'closures', 'decorations'}

def load_annotations(path):
    print(f"{path.name}: loading")
    with open(path) as f:
        data = json.load(f)

    print(f"{path.name}: n images = {len(data['images'])}, n annotations = {len(data['annotations'])}")
    return data

def main_category_ids(categories):
    main_ids = set()
    part_ids = set()

    for category in categories:
        if category['supercategory'] in part_supercategories:
            part_ids.add(category['id'])
        else:
            main_ids.add(category['id'])

    assert len(main_ids) == 27, f"expected 27 main apparel categories, got {len(main_ids)}"
    assert len(part_ids) == 19, f"expected 19 apparel parts, got {len(part_ids)}"

    print(f"categories: n main = {len(main_ids)}, n parts = {len(part_ids)}")
    return main_ids

def verify_ontology(train_data, val_data):
    train_categories = {category['id']: category['name'] for category in train_data['categories']}
    val_categories = {category['id']: category['name'] for category in val_data['categories']}
    train_attributes = {attribute['id']: attribute['name'] for attribute in train_data['attributes']}
    val_attributes = {attribute['id']: attribute['name'] for attribute in val_data['attributes']}
    
    if train_categories != val_categories:
        raise ValueError('category ontology differs between train and val')
    if train_attributes != val_attributes:
        raise ValueError('attribute ontology differs between train and val')
    
    print(f"ontology: n categories = {len(train_categories)}, n attributes = {len(train_attributes)}, train matches val")

def build_image_table(data, main_ids):
    main_apparel_image_ids = {
        annotation['image_id']
        for annotation in data['annotations']
        if annotation['category_id'] in main_ids
    }
    
    records = []
    
    for image in data['images']:
        if image['id'] not in main_apparel_image_ids:
            continue
        
        records.append({
            'image_id': image['id'],
            'file_name': image['file_name'],
            'width': image['width'],
            'height': image['height'],
            'license': image['license'],
        })
        
    images_df = pd.DataFrame(records)
    n_dropped = len(data['images']) - len(images_df)
    print(f"images: n indexed = {len(images_df)}, n dropped (parts only) = {n_dropped}")
    return images_df

def build_instance_tables(data, image_ids):
    instance_records = []
    attribute_records = []
    n_no_attributes = 0
    n_crowd = 0
    
    for annotation in data['annotations']:
        if annotation['image_id'] not in image_ids:
            continue
        
        bbox_x, bbox_y, bbox_w, bbox_h = annotation['bbox']
        
        instance_records.append({
            'instance_id': annotation['id'],
            'image_id': annotation['image_id'],
            'category_id': annotation['category_id'],
            'area': annotation['area'],
            'bbox_x': bbox_x,
            'bbox_y': bbox_y,
            'bbox_w': bbox_w,
            'bbox_h': bbox_h,
        })
        
        attribute_ids = sorted(set(annotation.get('attribute_ids', [])))
        
        if not attribute_ids:
            n_no_attributes += 1
        for attribute_id in attribute_ids:
            attribute_records.append({'instance_id': annotation['id'], 'attribute_id': attribute_id})
        
        if annotation['iscrowd'] == 1:
            n_crowd += 1
    
    instances_df = pd.DataFrame(instance_records)
    attributes_df = pd.DataFrame(attribute_records)
    
    print(f"instances: n = {len(instances_df)}, n without attributes = {n_no_attributes}, n iscrowd = {n_crowd}")
    print(f"instance attributes: n rows = {len(attributes_df)}")
    return instances_df, attributes_df

def verify_images_on_disk(images_df, image_dir):
    present_file_names = {path.name for path in image_dir.iterdir()}
    missing = []
    
    for file_name in images_df['file_name']:
        if file_name not in present_file_names:
            missing.append(file_name)
    
    print(f"image files: n found = {len(images_df) - len(missing)}, n missing = {len(missing)}")
    if missing:
        raise FileNotFoundError(f"{len(missing)} image files missing from {image_dir}, first few: {missing[:5]}")

if __name__ == '__main__':
    train_data = load_annotations(train_annotations_path)
    val_data = load_annotations(val_annotations_path)
    verify_ontology(train_data, val_data)

    main_ids = main_category_ids(train_data['categories'])
    images_df = build_image_table(train_data, main_ids)
    instances_df, attributes_df = build_instance_tables(train_data, set(images_df['image_id']))
    verify_images_on_disk(images_df, train_image_dir)
    
    processed_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        'images.csv': images_df,
        'instances.csv': instances_df,
        'instance_attributes.csv': attributes_df,
    }
    for filename, df in outputs.items():
        out_path = processed_dir / filename
        df.to_csv(out_path, index=False)
        print(f"{filename}: n rows = {len(df)}, saved to {out_path}")
