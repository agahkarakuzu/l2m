import l2m_lib
import os
import re
import argparse
from pathlib import Path

def process_directory(input_dir, output_dir, patterns_file):
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Process each .tex file in the input directory
    for filename in os.listdir(input_dir):
        if filename.endswith('.tex'):
            input_file = os.path.join(input_dir, filename)
            output_file = os.path.join(output_dir, filename.replace('.tex', '_l2m.md'))
            
            print(f"· Processing {input_file}")
            l2m_lib.main(input_file, output_file, patterns_file)
            print(f"↳ Output written to {output_file}")

def process_all_chapters(base_input_dir, base_output_dir, patterns_file):
    # Regular expression to match folder names like "01 My Chapter"
    #chapter_pattern = re.compile(r'^\d{2}\s+.*$')
    chapter_pattern = re.compile(r'^\d{2}[\s_].*$')

    for item in os.listdir(base_input_dir):
        full_path = os.path.join(base_input_dir, item)
        if os.path.isdir(full_path) and chapter_pattern.match(item):
            print(f"·· Looking at chapter: {item}")
            
            input_dir = full_path
            output_dir = os.path.join(base_output_dir, item)
            
            process_directory(input_dir, output_dir, patterns_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert LaTeX files to Markdown')
    parser.add_argument('--input', '-i', default=os.path.dirname(os.path.abspath(__file__)),
                       help='Base input directory containing chapter folders')
    parser.add_argument('--output', '-o', default=os.path.dirname(os.path.abspath(__file__)),
                       help='Base output directory for converted files')
    parser.add_argument('--patterns', '-p', default="l2m.yml",
                       help='Path to patterns YAML file')

    args = parser.parse_args()

    # Process all matching chapter folders
    process_all_chapters(args.input, args.output, args.patterns)

    print("----------------------\n","All transformations complete.","\n----------------------")