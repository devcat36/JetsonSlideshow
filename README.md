# JetsonSlideshow

A high-performance image and video slideshow viewer designed for NVIDIA Jetson Nano Development Kit, leveraging GStreamer for hardware-accelerated media playback.

## Features

- **Mixed Media Support**: Seamlessly displays both images and videos in a single slideshow
- **Hardware Acceleration**: Utilizes GStreamer for efficient media processing on Jetson hardware
- **Flexible Display Options**:
  - Configurable display interval for images
  - Automatic progression after video playback completion
  - Recursive directory scanning
  - Random shuffle mode
- **User-Friendly Interface**:
  - Fullscreen display
  - Auto-hiding cursor
  - ESC key to exit
- **Robust File Handling**:
  - Automatic EXIF orientation correction for images
  - Support for various image formats: JPG, JPEG, PNG, BMP, GIF
  - Support for video formats: MP4, AVI, MKV, MOV, WebM, FLV, WMV, MPG, MPEG
  - Graceful error handling with automatic skip on failed media

## Requirements

- Python 3
- GTK+ 3.0
- GStreamer 1.0 with plugins:
  - gstreamer1.0-plugins-base
  - gstreamer1.0-plugins-good
  - gstreamer1.0-plugins-bad
  - gstreamer1.0-plugins-ugly
- Python GObject introspection bindings

## Installation

1. Ensure your Jetson Nano is running JetPack with desktop environment

2. Install required dependencies:
```bash
sudo apt-get update
sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0
sudo apt-get install gstreamer1.0-tools gstreamer1.0-plugins-base \
                     gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
                     gstreamer1.0-plugins-ugly gstreamer1.0-libav
```

3. Clone or download the repository:
```bash
git clone https://github.com/devcat36/JetsonSlideshow.git
cd JetsonSlideshow
```

## Usage

Basic usage:
```bash
python3 slideshow.py <directory>
```

With options:
```bash
# Display each image for 3 seconds
python3 slideshow.py ~/Pictures --interval 3

# Search subdirectories recursively
python3 slideshow.py ~/Pictures --recursive

# Shuffle media files randomly
python3 slideshow.py ~/Pictures --shuffle

# Combine options
python3 slideshow.py ~/Pictures -r -s --interval 10
```

### Command Line Options

- `directory`: Path to directory containing media files (required)
- `--interval <seconds>`: Time to display each image in seconds (default: 5)
- `--recursive` or `-r`: Search subdirectories for media files
- `--shuffle` or `-s`: Randomize playback order

### Controls

- **ESC**: Exit the slideshow
- **Mouse Movement**: Temporarily shows cursor (auto-hides after 2 seconds)

## Technical Details

### Architecture

The application uses:
- **GTK+ 3.0** for the windowing system
- **GStreamer** for media pipeline management
- **X11 thread initialization** for stable video playback
- **Hardware-specific optimizations** for Jetson Nano

### Media Pipeline

- **Images**: Uses `imagefreeze` element to display static images with automatic orientation correction
- **Videos**: Employs `playbin` for most formats, with custom pipeline for AVI/MJPEG files
- **Rendering**: Uses `xvimagesink` for optimal performance on Jetson hardware

### Performance Considerations

- Designed specifically for Jetson Nano's hardware capabilities
- Efficient memory usage through proper GStreamer pipeline management
- Automatic cleanup of resources between media transitions

## Troubleshooting

### No media files found
- Verify the directory path exists and contains supported media files
- Check file permissions
- Try using the `--recursive` flag if files are in subdirectories

### Video playback issues
- Ensure all GStreamer plugins are installed
- Check if the video codec is supported by running:
  ```bash
  gst-inspect-1.0 | grep -i [codec_name]
  ```

### Display issues
- Verify X11 is running properly
- Check display permissions for the current user
- Ensure the Jetson is connected to a display

## License

This project is open source. Please check the license file for more details.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## Acknowledgments

Designed specifically for the NVIDIA Jetson Nano platform, taking advantage of its unique hardware capabilities for media processing.