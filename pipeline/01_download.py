import pathlib
import zipfile

import requests

repo_root = pathlib.Path(__file__).resolve().parents[1]
raw_dir = repo_root / 'data' / 'raw'

base_url = 'https://s3.amazonaws.com/ifashionist-dataset'

# Test images ship inside val_test2020.zip, but the test annotations aren't public,
# info_test2020.json only has image metadata. So only train and val can be used as
# an evaluation corpus (eval_protocol.md, section 2).
downloads = {
    'train2020.zip': f'{base_url}/images/train2020.zip',
    'val_test2020.zip': f'{base_url}/images/val_test2020.zip',
    'instances_attributes_train2020.json': f'{base_url}/annotations/instances_attributes_train2020.json',
    'instances_attributes_val2020.json': f'{base_url}/annotations/instances_attributes_val2020.json',
    'info_test2020.json': f'{base_url}/annotations/info_test2020.json',
}

archives = ['train2020.zip', 'val_test2020.zip']


def get_remote_size(url):
    response = requests.head(url, allow_redirects=True, timeout=30)
    response.raise_for_status()
    return int(response.headers.get('content-length', 0))


def download_file(url, dest_path):
    remote_size = get_remote_size(url)
    remote_mb = remote_size / 1048576

    # Checks the file size against content-length, not just whether the file exists,
    # so a download that got cut off partway gets re-fetched instead of being treated
    # as complete.
    if dest_path.exists() and dest_path.stat().st_size == remote_size:
        print(f"{dest_path.name}: already complete, size = {remote_mb:.1f} MB")
        return

    print(f"{dest_path.name}: downloading, size = {remote_mb:.1f} MB")
    bytes_downloaded = 0
    last_reported_percent = 0

    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1048576):
                f.write(chunk)
                bytes_downloaded += len(chunk)
                percent = bytes_downloaded / remote_size * 100 if remote_size else 0
                if percent - last_reported_percent >= 5:
                    print(f"  {percent:.0f}%")
                    last_reported_percent = percent

    # A size mismatch after the download finishes means the file is truncated
    # (or an error page got saved instead), so fail here rather than try to
    # extract a broken zip later.
    if remote_size and dest_path.stat().st_size != remote_size:
        raise IOError(f"{dest_path.name}: expected {remote_size} bytes, got {dest_path.stat().st_size}")

    print(f"{dest_path.name}: done")


def extract_archive(zip_path, dest_dir):
    with zipfile.ZipFile(zip_path) as zf:
        member_names = zf.namelist()
        n_members = len(member_names)

        # The archives have their own top-level folder (train2020.zip -> train/),
        # so extracting into raw_dir keeps the images in a subfolder instead of
        # dumping thousands of files straight into data/raw/.
        n_already_extracted = sum(1 for name in member_names if (dest_dir / name).exists())
        if n_already_extracted == n_members:
            print(f"{zip_path.name}: already extracted, n entries = {n_members}")
            return

        print(f"{zip_path.name}: extracting, n entries = {n_members}")
        zf.extractall(dest_dir)
        print(f"{zip_path.name}: done")


def download_fashionpedia():
    for filename, url in downloads.items():
        download_file(url, raw_dir / filename)

    for filename in archives:
        extract_archive(raw_dir / filename, raw_dir)


if __name__ == '__main__':
    raw_dir.mkdir(parents=True, exist_ok=True)
    download_fashionpedia()

    print(f"\nraw data in {raw_dir}")
    for path in sorted(raw_dir.iterdir()):
        if path.is_dir():
            n_files = sum(1 for child in path.rglob('*') if child.is_file())
            print(f"{path.name}/: n files = {n_files}")
        else:
            print(f"{path.name}: size = {path.stat().st_size / 1048576:.1f} MB")
