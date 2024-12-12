#!/usr/bin/env python3
import re
import yaml
import argparse
import random
import string
from datetime import datetime  # Add this import for date handling

def load_patterns(yaml_file):
    """
    Loads the patterns from the YAML file.
    - The YAML file is used to define the patterns for the transformations.
    - If pre-processing is needed, it is handled here (e.g., escape)

    """
    with open(yaml_file, 'r') as file:
        yaml_data = yaml.safe_load(file)
    
    patterns = []
    for pattern in yaml_data['substitutions']:
        start = pattern['start']
        end = pattern['end']
        if pattern.get('escape', True):
            start = re.escape(start)
            end = re.escape(end)

        regex = start + r'\s*([\s\S]*?)\s*' + end
        flags = re.MULTILINE | re.DOTALL if 'DOTALL' in pattern.get('flags', []) else re.MULTILINE
        directive = pattern['directive']
        extract_label = pattern.get('extract_label', False)
        generate_front_matter = pattern.get('generate_front_matter', False)
        replacement = pattern.get('replacement', None)
        delimiter = pattern.get('delimiter', None)
        split_prefix = pattern.get('split_prefix', None)
        sanitize = pattern.get('sanitize', False)
        try:
            compiled_regex = re.compile(regex, flags)
            patterns.append({
                'regex': compiled_regex,
                'directive': directive,
                'extract_label': extract_label,
                'generate_front_matter': generate_front_matter,
                'replacement': replacement,
                'name': pattern.get('name', 'unnamed'),
                'delimiter': delimiter,
                'split_prefix': split_prefix,
                'sanitize': sanitize
            })
        except re.error as e:
            print(f"Error compiling regex for pattern '{pattern.get('name', 'unnamed')}': {e}")
            print(f"Problematic regex: {regex}")
            print("Skipping this pattern.")
    
    return patterns, yaml_data.get('remove_commands', []), yaml_data.get('remove_comments', False)
    
def sanitize(s):
    """
    Sanitizes the input string by replacing certain characters with others.
    - This is needed for proper equation/figure etc labels.
    """
    return s.translate(str.maketrans('=)(', '---'))

def process_eqsand(content):
    def eqsand_replacement(match):
        return f"{{{{numref}}}}``Eq. (PERCENT_S) <{match.group(1)}>`` and {{{{numref}}}}``Eq. (PERCENT_S) <{match.group(2)}>`"
    
    return re.sub(r'\\eqsand{(.*?)}{(.*?)}', eqsand_replacement, content)

def transform_problem_to_exercise(content):
    """
    Transforms \prob{...} to an exercise directive.
    - Assumption: \prob{...} blocks are successive 
    - The problems section is followed by a \section{} or # Solutions
      - \section or # depends on in which order the content is processed
    """
    pattern = r'\\prob{(.*?)}{(.*?)}(.*?)(?=\\prob|\\section|$|# Solutions)'
    replacement = r'\n::::{exercise} \1\n:label: \2\n\n\3::::\n'
    return re.sub(pattern, replacement, content, flags=re.DOTALL)

def transform_problem_to_solution(content):
    """
    Transforms \sol{...} to a collapsible solution directive.
    - Assumption: \sol{...} blocks are successive 
    - The solution section is followed by a \section{} or # Summary 
      - \section or # depends on in which order the content is processed
    """
    pattern = r'\\sol{(.*?)}(.*?)(?=\\sol|\\section|$|# Summary)'
    replacement = r'\n::::{solution} \1 \n:label: \1-sol\n:class: dropdown\n\2::::\n'
    return re.sub(pattern, replacement, content, flags=re.DOTALL)

def process_figure(matched_content, folder):
    """
    Transforms a latex figure directive to a myst figure directive.
    - \begin{figure}[h]...\end{figure} becomes :::{figure}... :::
    - \includegraphics becomes ![](./folder/filename) 
        - Multiple \includegraphics are handled as subfigures
    """
    label_match = re.search(r'\\label{(.*?)}', matched_content)
    caption_match = re.search(r'\\caption{((?:[^{}]|{(?:[^{}]|{[^{}]*})*})*?)}', matched_content, re.DOTALL)
    includegraphics_matches = re.findall(r'\\includegraphics(?:\[.*?\])?\{(.*?)\}', matched_content)

    label = label_match.group(1) if label_match else ''
    caption = caption_match.group(1) if caption_match else ''
    caption = re.sub(r'\\label{.*?}', '', caption).strip()

    if len(includegraphics_matches) == 1:
        filename = includegraphics_matches[0]
        return f":::" + "{figure} " + f"{folder}{filename}\n:label: {label}\n:align: center\n\n{caption}\n:::"
    else:
        figure_content = ":::{figure}" + f"\n:label: {label}\n:align: center\n\n"
        for filename in includegraphics_matches:
            figure_content += f"![]({folder}{filename})\n"
        figure_content += f"\n{caption}\n:::"
        return figure_content

def extract_label_from_content(content):
    """
    Extracts the label from the content.
    - The label is extracted from the first \label{...} directive
    - The content is cleaned of the label directive
    - The label is sanitized
    """
    label_match = re.search(r'\\label{(.*?)}', content)
    if label_match:
        label = label_match.group(1)
        content = re.sub(r'\\label{.*?}', '', content).strip()
        return label, content
    return None, content

def remove_latex_commands(content, commands_to_remove):
    """
    Removes the specified LaTeX commands from the content.
    - Certain latex commands are not needed to be transformed into myst directives
    - Redundant commands are removed using this option
    """
    for command in commands_to_remove:
        print(f"Removing command: {command}")
        #content = re.sub(rf'\\{command}(?={{|\s|$)', '', content)
        content = re.sub(rf'\\{command}(?=\s|$|[^a-zA-Z])', '', content)
    return content

def remove_latex_comments(content):
    """
    Removes the LaTeX comments from the content.
    - Comments are removed but \% is kept intact
    """
    content = re.sub(r'(?<!\\)%.*', '', content)
    return content

def replace_latex_quotes(content):
    """
    Fixes the funky quotes from the latex source
    - ``text'' becomes "text"
    - ``text" becomes "text"
    - `text' becomes 'text'
    """
    content = re.sub(r"``(.*?)''", r'"\1"', content)
    content = re.sub(r"``(.*?)\"", r'"\1"', content)
    content = re.sub(r"`(.*?)'", r"'\1'", content)
    return content

def generate_random_label(length=5):
    """
    Generates a random label of a given length.
    - The label is used for footnote labels
    """
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def transform_markdown(content, patterns, commands_to_remove, remove_comments):
    """
    Transforms the content using the patterns.
    - The content is transformed using the directives defined in the patterns file
    - The content is cleaned of the LaTeX commands defined in the patterns file
    - The content is cleaned of the LaTeX comments
    - The content is processed for footnotes
    - The content is transformed into a Markdown file
    """
    front_matter = ""
    footnotes = []
    footnote_pattern = re.compile(r'\\footnote{((?:[^{}]|{(?:[^{}]|{[^{}]*})*})*?)}', re.DOTALL)
    
    def footnote_replacement(match):
        """
        Replaces the footnote directive with a footnote label.
        - The footnote label is generated randomly
        - The footnote content is indented
        - The footnote label and content are stored in the footnotes list
        """
        footnote_content = match.group(1).strip()
        label = generate_random_label()
        lines = footnote_content.split('\n')
        indented_lines = [lines[0]] + ['    ' + line for line in lines[1:]]
        indented_content = '\n'.join(indented_lines)
        footnotes.append(f"[^{label}]: {indented_content}")
        return f"[^{label}]"

    def replacement_function(match):
        """
        The main loop that replaces the matched content with the directive content.
        """
        for pattern in patterns:
            if pattern['regex'].pattern == match.re.pattern:
                matched_content = match.group(1).strip()
                directive = pattern['directive']
                if pattern.get('generate_front_matter'):
                    nonlocal front_matter
                    title = matched_content
                    date = datetime.now().strftime('%Y-%m-%d')
                    front_matter = f"---\ntitle: \"{title}\" \ndate: {date}\n---\n\n"
                    return ''
                
                elif directive.get('type') == 'inline':
                    replacement = pattern.get('replacement', '{content}')
                    if pattern['sanitize']:
                        matched_content = sanitize(matched_content)
                    if pattern['delimiter']:
                        delimiter = pattern['delimiter']
                        items = matched_content.split(delimiter)
                        transformed_items = [item.strip() for item in items]
                        transformed_items[1:] = [f"{pattern['split_prefix']}{item}" for item in transformed_items[1:]]
                        matched_content = ";".join(transformed_items)
                    return replacement.format(content=matched_content)

                elif directive.get('type') == 'figure':
                    folder = directive.get('folder', '../static/')
                    return process_figure(matched_content, folder)
                
                elif directive.get('type') == 'hint':
                    return f"\n```{{hint}}\n:class: dropdown\n{matched_content}\n```\n"

                elif directive.get('type') == 'card':
                    matched_content = re.sub(r'\\item\s*', '', matched_content)
                    return f"\n:::{{card}}\n{matched_content}\n:::\n"

                elif directive.get('type') == 'itemize':
                    items = re.split(r'\\item\s*', matched_content)
                    items = [item.strip() for item in items if item.strip()]
                    output = ""
                    for i, item in enumerate(items):
                        if pattern.get('name') == 'itemize_alphabold':
                            letter = chr(97 + i)  # 97 is the ASCII code for 'a'
                            output += f"\n\n**({letter})** {item}\n\n"
                        elif pattern.get('name') == 'itemize_vanilla':
                            output += f"\n\n* {item}\n\n"
                        else:
                            output += f"\n\n* {item}\n\n"
                    return output.strip()

                else:
                    if pattern['extract_label']:
                        label, matched_content = extract_label_from_content(matched_content)
                        #print(f"Extracted label: {label}")
                        if label:
                            directive['label'] = sanitize(label)
                    output = f"```{{{directive['type']}}}\n"
                    for key, value in directive.items():
                        if key != 'type':
                            output += f":{key}: {value}\n"
                    output += f"{matched_content}\n```"
                    return output
        return match.group(0)

    for pattern in patterns:
        content = pattern['regex'].sub(replacement_function, content)

    # Remove specified LaTeX commands
    content = remove_latex_commands(content, commands_to_remove)
    # Fix the funky quotes from the latex source
    content = replace_latex_quotes(content)

    # Remove LaTeX comments if specified
    if remove_comments:
        content = remove_latex_comments(content)

    # Process footnotes
    content = footnote_pattern.sub(footnote_replacement, content)

    if footnotes:
        content += "\n\n" + "\n".join(footnotes)
    
    content = replace_latex_quotes(content)
    content = transform_problem_to_exercise(content)
    content = transform_problem_to_solution(content)

    content = process_eqsand(content)
    # Replace PERCENT_S with %s, needed for the equation numbering
    content = re.sub(r'PERCENT_S', '%s', content)

    return front_matter + content

def main(input_file, output_file, patterns_file):
    patterns, commands_to_remove, remove_comments = load_patterns(patterns_file)
    
    with open(input_file, 'r') as f:
        content = f.read()
    
    transformed_content = transform_markdown(content, patterns, commands_to_remove, remove_comments)
    
    with open(output_file, 'w') as f:
        f.write(transformed_content)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transform Markdown files using patterns from YAML.")
    parser.add_argument("input_file", help="Path to the input Markdown file")
    parser.add_argument("output_file", help="Path to the output Markdown file")
    parser.add_argument("--patterns", default="l2m.yml", help="Path to the patterns YAML file")
    args = parser.parse_args()

    main(args.input_file, args.output_file, args.patterns)