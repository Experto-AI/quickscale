#!/bin/bash

# compile_docs.sh
# Process all files in docs/contrib in order and generate CONTRIBUTING.md
# Creates an index with links to external files without including their content

OUTPUT_FILE="CONTRIBUTING.md"
CONTRIB_DIR="docs/contrib"
CURSOR_RULES_DIR=".cursor/rules"

# Create .cursor/rules directory if it doesn't exist
mkdir -p "$CURSOR_RULES_DIR"

# Delete all files inside .cursor/rules
echo "Cleaning $CURSOR_RULES_DIR directory..."
rm -f "$CURSOR_RULES_DIR"/*

echo "# Contributing Guidelines" > $OUTPUT_FILE
echo "" >> $OUTPUT_FILE
echo "This document outlines the coding standards and guidelines for contributing to this project." >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE
echo "## Table of Contents" >> $OUTPUT_FILE

# Process each file to create index entries
for file in $(ls -1 $CONTRIB_DIR/*.md | sort); do
    echo "Processing $file for index..."
    
    # Get file path relative to the root directory for linking
    rel_path="docs/contrib/$(basename "$file")"
    
    # Get the first heading (title) from the file
    title=$(grep -E "^# " "$file" | head -n 1 | sed -E 's/^# //')
    
    # If no title found, generate one from filename
    if [ -z "$title" ]; then
        filename=$(basename "$file")
        title=$(echo "$filename" | sed -E 's/^[0-9]+_//' | sed -E 's/\.md$//' | tr '_' ' ' | sed -E 's/\b\w/\U&/g')
    fi
    
    # Add entry for the file with link to the file
    echo "- [$title]($rel_path)" >> $OUTPUT_FILE
    
    # Extract subheadings (level 2 through 5) and add as indented list items
    echo "Extracting headings from $file..." >> /tmp/compile_docs_debug.log
    grep -E "^[ ]*#{2,5}[ ]+" "$file" | while read -r line; do
        echo "Found heading: $line" >> /tmp/compile_docs_debug.log
        heading_level=$(echo "$line" | grep -o "^[ ]*#\+" | tr -d ' ' | wc -c)
        heading_text=$(echo "$line" | sed -E 's/^[ ]*#+ *//')
        
        echo "Level: $heading_level, Text: $heading_text" >> /tmp/compile_docs_debug.log
        
        # Add proper indentation based on heading level
        indent=""
        for ((i=2; i<heading_level; i++)); do
            indent="  $indent"
        done
        
        # Only create links for level 2 headings with simple numbers like "2."
        # Match patterns like "2. Title" but not "2.1. Title" or "2.2.1. Title"
        if [ $heading_level -eq 2 ] && [[ $heading_text =~ ^[0-9]+\.\s ]]; then
            anchor=$(echo "$heading_text" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-zA-Z0-9]+/-/g' | sed -E 's/^-+|-+$//g')
            echo "  $indent- [$heading_text]($rel_path#$anchor)" >> $OUTPUT_FILE
        else
            # For other subheadings, don't create links
            echo "  $indent- $heading_text" >> $OUTPUT_FILE
        fi
    done
    
    # Create .mdc file with YAML frontmatter in .cursor/rules directory
    base_filename=$(basename "$file" .md)
    target_file="$CURSOR_RULES_DIR/${base_filename}.mdc"
    
    # Generate description from filename (remove numbers, underscores, and extension)
    description=$(echo "$base_filename" | sed -E 's/^[0-9]+_//' | tr '_' ' ' | tr '[:upper:]' '[:lower:]')
    
    # Create new .mdc file with frontmatter
    echo "---" > "$target_file"
    echo "description: $description" >> "$target_file"
    echo "globs: " >> "$target_file"
    echo "alwaysApply: false" >> "$target_file"
    echo "---" >> "$target_file"
    echo "" >> "$target_file"
    
    # Append original file content
    cat "$file" >> "$target_file"
    
    echo "Created .mdc file for $file in $CURSOR_RULES_DIR as ${base_filename}.mdc with frontmatter"
done

echo "" >> $OUTPUT_FILE
echo "Documentation index compiled successfully to $OUTPUT_FILE"
echo "Markdown files with YAML frontmatter created in $CURSOR_RULES_DIR"
