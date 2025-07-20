import os
from datetime import datetime
import pandas as pd
from pypdf import PdfReader, PdfWriter

def ask(prompt, default=None):
    if default:
        prompt += f" [{default}]: "
    else:
        prompt += ": "
    value = input(prompt).strip()
    return value or default

def ask_yes_no(prompt, default="y"):
    while True:
        value = input(f"{prompt} (y/n) [{default}]: ").strip().lower() or default
        if value in ["y", "n"]:
            return value == "y"
        print("Please enter 'y' or 'n'.")

def split_pdf_by_page_count(
    pdf_path,
    csv_path,
    output_dir,
    pages_per_split,
    prefix="",
    suffix="",
    dry_run=False,
    overwrite=False,
    password=None
):
    output_paths = []

    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
    except Exception as e:
        print(f"❌ Failed to read PDF file: {e}")
        return []

    try:
        names = pd.read_csv(csv_path, header=None).dropna().squeeze().tolist()
        if not isinstance(names, list):
            names = [names]
    except Exception as e:
        print(f"❌ Failed to read CSV: {e}")
        return []

    num_splits = (total_pages + pages_per_split - 1) // pages_per_split
    name_count = len(names)

    os.makedirs(output_dir, exist_ok=True)

    for i in range(num_splits):
        start = i * pages_per_split
        end = min((i + 1) * pages_per_split, total_pages)
        writer = PdfWriter()

        for j in range(start, end):
            writer.add_page(reader.pages[j])

        if password:
            writer.encrypt(password)

        # Use name from CSV if available, else fallback
        if i < name_count:
            name = names[i].strip().replace(" ", "_")
        else:
            name = f"Split{i+1}"

        filename = f"{prefix}{name}{suffix}.pdf"
        filepath = os.path.join(output_dir, filename)

        if dry_run:
            print(f"[Dry Run] Would create: {filepath} (Pages {start+1}-{end})")
        else:
            if os.path.exists(filepath) and not overwrite:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                filepath = filepath.replace(".pdf", f"_{timestamp}.pdf")
                print(f"⚠️ File exists. Renamed to: {filepath}")
            with open(filepath, "wb") as f_out:
                writer.write(f_out)
            output_paths.append(filepath)
            print(f"✅ Created: {filepath} (Pages {start+1}-{end})")

    return output_paths

def main():
    print("📄 PDF Splitter – Interactive CLI Version\n")

    # Always look in the script's own directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(script_dir, "input.pdf")
    csv_path = os.path.join(script_dir, "names.csv")
    output_dir = script_dir  # Save to the same folder

    if not os.path.isfile(pdf_path):
        print("❌ 'input.pdf' not found in the script directory.")
        return

    if not os.path.isfile(csv_path):
        print("❌ 'names.csv' not found in the script directory.")
        return

    print(f"📂 Output will be saved in the same folder as this script: {output_dir}")

    pages_per_split = int(ask("Enter number of pages per split", default="5"))
    prefix = ask("Enter prefix for output filenames", default="")
    suffix = ask("Enter suffix for output filenames", default="")
    dry_run = ask_yes_no("Enable dry run (preview only)?", default="n")
    overwrite = ask_yes_no("Allow overwriting existing files?", default="n")
    use_password = ask_yes_no("Protect PDFs with a password?", default="n")
    password = ask("Enter password") if use_password else None

    split_pdf_by_page_count(
        pdf_path=pdf_path,
        csv_path=csv_path,
        output_dir=output_dir,
        pages_per_split=pages_per_split,
        prefix=prefix,
        suffix=suffix,
        dry_run=dry_run,
        overwrite=overwrite,
        password=password
    )

if __name__ == "__main__":
    main()
