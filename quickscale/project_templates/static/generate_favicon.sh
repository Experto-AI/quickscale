#!/bin/bash

# This script converts favicon.svg to favicon.ico
# It requires ImageMagick to be installed: apt-get install imagemagick

if command -v convert > /dev/null; then
  echo "Converting favicon.svg to favicon.ico..."
  
  # Generate favicon.ico from the SVG
  convert -background transparent \
          -density 256x256 \
          favicon.svg \
          -define icon:auto-resize=64,48,32,16 \
          favicon.ico
          
  echo "Favicon conversion complete!"
else
  echo "ImageMagick not found. Please install it to convert SVG to ICO:"
  echo "  sudo apt-get install imagemagick"
fi 