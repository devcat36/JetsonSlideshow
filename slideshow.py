#!/usr/bin/env python3
"""
Jetson Slideshow - Image and Video Slideshow Viewer for Jetson Nano Development Kit

Usage: python3 slideshow.py <directory> [--interval <seconds>] [--recursive | -r] [--shuffle | -s]
Example: python3 slideshow.py ~/images --interval 3
         python3 slideshow.py ~/media -r -s
"""

# Initialize X11 threads FIRST before any other imports
import ctypes
import sys
if sys.platform.startswith('linux'):
    try:
        x11 = ctypes.cdll.LoadLibrary('libX11.so')
        x11.XInitThreads()
        print("X11 threads initialized")
    except:
        print("Warning: Failed to initialize X11 threads")

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')

from gi.repository import Gtk, Gst, GLib, GdkX11, GstVideo, Gdk
import os
import glob
import time
import argparse
import random

class MediaSlideshowViewer(Gtk.Window):
    def __init__(self, media_directory, image_interval=5, recursive=False, shuffle=False):
        super().__init__(title="GStreamer Media Slideshow Viewer")

        # Set window type hint for better focus management
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)

        self.fullscreen()
        self.connect("destroy", self.on_destroy)
        self.connect("key-press-event", self.on_key_press)
        self.connect("motion-notify-event", self.on_mouse_move)
        self.connect("realize", self.on_realize)

        # Cursor hiding
        self.cursor_hide_timeout = None
        self.blank_cursor = None

        # Check for required plugins
        registry = Gst.Registry.get()
        if not registry.find_plugin("playback"):
            print("Warning: GStreamer playback plugin not found. Video playback may not work.")
            print("Install with: sudo apt-get install gstreamer1.0-plugins-base")

        # Expand user home directory if present
        media_directory = os.path.expanduser(media_directory)

        # Initialize attributes
        self.timeout_id = None

        # Get list of media files
        self.media_files = []

        # Image extensions
        image_exts = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.gif']
        # Video extensions
        video_exts = ['*.mp4', '*.avi', '*.mkv', '*.mov', '*.webm', '*.flv', '*.wmv', '*.mpg', '*.mpeg']

        if recursive:
            print(f"Searching recursively for media files in: {media_directory}")
            for ext in image_exts + video_exts:
                pattern = os.path.join(media_directory, '**', ext)
                self.media_files.extend(glob.glob(pattern, recursive=True))
                # Also search for uppercase extensions
                self.media_files.extend(glob.glob(pattern.replace(ext, ext.upper()), recursive=True))
        else:
            print(f"Looking for media files in: {media_directory}")
            for ext in image_exts + video_exts:
                self.media_files.extend(glob.glob(os.path.join(media_directory, ext)))
                # Also search for uppercase extensions
                self.media_files.extend(glob.glob(os.path.join(media_directory, ext.upper())))

        # Initialize all attributes before checking files
        self.current_index = 0
        self.image_interval = image_interval  # Interval for images in seconds
        self.pipeline = None
        self.bus = None
        self.is_video = False
        self.recursive = recursive  # Store for logging
        self.shuffle = shuffle  # Store for logging
        self.media_directory = media_directory  # Store for relative path display

        # Define video extensions for checking
        self.video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv', '.mpg', '.mpeg']

        if not self.media_files:
            print(f"No media files found in {media_directory}")
            self.destroy()
            return

        # Sort or shuffle files
        if shuffle:
            random.shuffle(self.media_files)
            print("Media files shuffled")
        else:
            self.media_files.sort()  # Sort files alphabetically

        print(f"Found {len(self.media_files)} media files:")

        # Show file list (limited to 20 to avoid spam)
        files_to_show = self.media_files[:20] if len(self.media_files) > 20 else self.media_files

        if recursive:
            # Show files with relative paths when recursive
            for media in files_to_show:
                media_type = "video" if self.is_video_file(media) else "image"
                rel_path = os.path.relpath(media, media_directory)
                print(f"  - {rel_path} ({media_type})")
        else:
            # Show just filenames when not recursive
            for media in files_to_show:
                media_type = "video" if self.is_video_file(media) else "image"
                print(f"  - {os.path.basename(media)} ({media_type})")

        if len(self.media_files) > 20:
            print(f"  ... and {len(self.media_files) - 20} more files")

        if shuffle:
            print("\nPlayback order: shuffled")

        # Create drawing area for video
        self.drawing_area = Gtk.DrawingArea()
        # Set black background
        self.drawing_area.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(0, 0, 0, 1))
        self.add(self.drawing_area)

        # Show all widgets first
        self.show_all()

        # Enable motion events for cursor hiding
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK)

        # Use idle_add to ensure thread safety when realizing
        GLib.idle_add(self.initialize_media)

    def on_realize(self, widget):
        """Called when window is realized - set up blank cursor"""
        # Create a blank cursor for hiding
        display = self.get_display()
        self.blank_cursor = Gdk.Cursor.new_for_display(display, Gdk.CursorType.BLANK_CURSOR)

        # Hide cursor initially
        self.hide_cursor()

    def hide_cursor(self):
        """Hide the mouse cursor"""
        if self.blank_cursor:
            window = self.get_window()
            if window:
                window.set_cursor(self.blank_cursor)
        self.cursor_hide_timeout = None
        return False

    def show_cursor(self):
        """Show the mouse cursor"""
        window = self.get_window()
        if window:
            window.set_cursor(None)  # Reset to default cursor

        # Cancel any existing timeout
        if self.cursor_hide_timeout:
            GLib.source_remove(self.cursor_hide_timeout)

        # Set timeout to hide cursor again after 2 seconds
        self.cursor_hide_timeout = GLib.timeout_add_seconds(2, self.hide_cursor)

    def on_mouse_move(self, widget, event):
        """Handle mouse movement - show cursor temporarily"""
        self.show_cursor()
        return False

    def on_key_press(self, widget, event):
        """Handle key press events"""
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
        return False

    def initialize_media(self):
        """Initialize media loading - called from main thread"""
        # Realize the drawing area to ensure we can get window handle
        self.drawing_area.realize()

        # Ensure window is focused at startup
        self.ensure_window_focused()

        # Create initial pipeline
        self.load_current_media()

        return False  # Don't repeat

    def is_video_file(self, filepath):
        """Check if the file is a video based on extension"""
        return any(filepath.lower().endswith(ext) for ext in self.video_extensions)

    def clear_drawing_area(self):
        """Clear the drawing area to black"""
        if self.drawing_area.get_window():
            # Get the window and create a cairo context
            window = self.drawing_area.get_window()
            width = window.get_width()
            height = window.get_height()

            # Create a cairo context and paint it black
            cr = window.cairo_create()
            cr.set_source_rgb(0, 0, 0)  # Black
            cr.rectangle(0, 0, width, height)
            cr.fill()

    def cleanup_pipeline(self):
        """Properly cleanup the existing pipeline"""
        if self.pipeline:
            print("Cleaning up previous pipeline...")

            # Cancel any pending timeout
            if self.timeout_id:
                GLib.source_remove(self.timeout_id)
                self.timeout_id = None

            # Stop the pipeline
            self.pipeline.set_state(Gst.State.NULL)

            # Remove bus watch
            if self.bus:
                self.bus.remove_signal_watch()
                self.bus = None

            # Wait for state change to complete
            self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

            # Unreference the pipeline
            self.pipeline = None

    def create_pipeline(self, media_path):
        # Clean up existing pipeline
        self.cleanup_pipeline()

        self.is_video = self.is_video_file(media_path)
        media_type = "video" if self.is_video else "image"

        # Show relative path if recursive, otherwise just filename
        if self.recursive:
            display_name = os.path.relpath(media_path, self.media_directory)
        else:
            display_name = os.path.basename(media_path)

        print(f"\nLoading {media_type}: {display_name}")

        try:
            # Create different pipelines for images and videos
            if self.is_video:
                # Check if it's an AVI file (likely MJPEG) to avoid playbin segfault
                if media_path.lower().endswith('.avi'):
                    print("Using custom pipeline for AVI/MJPEG file...")

                    # Use jpegdec for MJPEG in AVI files
                    pipeline_string = f"""
                        filesrc location="{media_path}" !
                        avidemux !
                        jpegdec !
                        videoconvert !
                        autovideosink name=sink
                    """

                    # Parse and create pipeline
                    self.pipeline = Gst.parse_launch(pipeline_string)

                    # For AVI files with autovideosink, we don't get the sink element
                    # The window handle will be set via sync message
                else:
                    # Use playbin for other video formats
                    print("Creating video pipeline with playbin...")

                    self.pipeline = Gst.ElementFactory.make("playbin", "player")
                    if not self.pipeline:
                        print("Failed to create playbin")
                        return False

                    # Set the file URI
                    file_uri = "file://" + os.path.abspath(media_path)
                    self.pipeline.set_property("uri", file_uri)

                    # Don't set video-sink - let playbin choose the best one
                    print("Using playbin with automatic sink selection")
            else:
                # Image pipeline with automatic orientation handling
                if media_path.lower().endswith(('.jpg', '.jpeg')):
                    # For JPEG images, use jpegparse to handle EXIF orientation
                    pipeline_string = f"""
                        filesrc location="{media_path}" !
                        jpegparse !
                        jpegdec !
                        videoconvert !
                        videoflip method=automatic !
                        videoscale !
                        video/x-raw,format=RGB !
                        imagefreeze !
                        videoconvert !
                        xvimagesink name=sink force-aspect-ratio=true
                    """
                else:
                    # For other formats, use decodebin which may handle orientation
                    pipeline_string = f"""
                        filesrc location="{media_path}" !
                        decodebin !
                        videoconvert !
                        videoflip method=automatic !
                        videoscale !
                        video/x-raw,format=RGB !
                        imagefreeze !
                        videoconvert !
                        xvimagesink name=sink force-aspect-ratio=true
                    """

                # Parse and create pipeline for images
                self.pipeline = Gst.parse_launch(pipeline_string)

                # Get the sink element for images
                self.sink = self.pipeline.get_by_name("sink")

            # Set up bus for messages
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.enable_sync_message_emission()
            self.bus.connect("sync-message::element", self.on_sync_message)
            self.bus.connect("message", self.on_message)
            self.bus.connect("message::error", self.on_error)
            self.bus.connect("message::eos", self.on_eos)
            self.bus.connect("message::state-changed", self.on_state_changed)

            # Start playing
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                print("Failed to start pipeline")
                return False
            else:
                print("Pipeline started successfully")

                # For images, set timeout to change after interval
                # For videos, we'll wait for EOS
                if not self.is_video:
                    print(f"Will change to next media in {self.image_interval} seconds")
                    self.timeout_id = GLib.timeout_add_seconds(self.image_interval, self.change_media)
                else:
                    print("Playing video to completion...")

                return True

        except Exception as e:
            print(f"Error creating pipeline: {e}")
            return False

    def on_sync_message(self, bus, message):
        if message.get_structure() is None:
            return

        message_name = message.get_structure().get_name()
        if message_name == "prepare-window-handle":
            # Use GLib.idle_add to ensure we're on the main GTK thread
            GLib.idle_add(self.set_window_handle, message)

    def set_window_handle(self, message):
        """Set the window handle for video output - called from main thread"""
        print("Setting window handle")

        # Ensure drawing area is realized
        if not self.drawing_area.get_realized():
            self.drawing_area.realize()

        win = self.drawing_area.get_window()
        if win:
            xid = win.get_xid()
            # Always set on message source - works for playbin, autovideosink, and xvimagesink
            message.src.set_window_handle(xid)

        return False  # Don't repeat the idle callback

    def on_message(self, bus, message):
        """Handle general GStreamer messages"""
        msg_type = message.type

        if msg_type == Gst.MessageType.ERROR:
            # Let the specific error handler deal with it
            pass
        elif msg_type == Gst.MessageType.EOS:
            # Let the specific EOS handler deal with it
            pass
        elif msg_type == Gst.MessageType.BUFFERING:
            # Handle buffering for smooth playback
            percent = message.parse_buffering()
            if percent < 100:
                self.pipeline.set_state(Gst.State.PAUSED)
            else:
                self.pipeline.set_state(Gst.State.PLAYING)

    def on_state_changed(self, bus, message):
        if message.src == self.pipeline:
            old_state, new_state, pending_state = message.parse_state_changed()
            if new_state == Gst.State.PLAYING:
                pass  # Pipeline is playing successfully

    def on_error(self, bus, message):
        err, debug = message.parse_error()
        print(f"Error: {err}")
        print(f"Debug: {debug}")

        # Skip to next media immediately on error
        print(f"Error occurred, skipping to next media...")
        self.change_media()

    def on_eos(self, bus, message):
        print("End of stream - media finished playing")
        # When video ends, automatically move to next media
        if self.is_video:
            print("Video completed, moving to next media...")
            self.change_media()

    def ensure_window_focused(self):
        """Ensure the window is focused and on top"""
        # Present the window (brings to front and focuses)
        self.present()

        # Also try to grab focus
        self.grab_focus()

        # For some window managers, we might need to be more aggressive
        # Set the window to be always on top temporarily
        self.set_keep_above(True)

        # Use idle_add to reset keep_above after a short time
        # This ensures we get focus but don't permanently stay on top
        def reset_keep_above():
            self.set_keep_above(False)
            return False

        GLib.timeout_add(100, reset_keep_above)

        # Hide cursor when focusing window (if window is realized)
        if self.blank_cursor:
            self.hide_cursor()

    def load_current_media(self):
        """Try to load the current media file, skip if it fails"""
        # Ensure window is focused
        self.ensure_window_focused()

        attempts = 0
        while attempts < len(self.media_files):
            current_file = self.media_files[self.current_index]

            # Only clear the drawing area if we're about to play a video
            if self.is_video_file(current_file):
                self.clear_drawing_area()

            if self.create_pipeline(current_file):
                # Success
                break
            else:
                # Failed, try next media
                if self.recursive:
                    display_name = os.path.relpath(current_file, self.media_directory)
                else:
                    display_name = os.path.basename(current_file)
                print(f"Failed to load {display_name}, trying next...")
                self.current_index = (self.current_index + 1) % len(self.media_files)
                attempts += 1

        if attempts >= len(self.media_files):
            print("Could not load any media files!")
            self.destroy()

    def change_media(self):
        print(f"\nChanging to next media...")

        # Move to next media file
        self.current_index = (self.current_index + 1) % len(self.media_files)

        # Load the current media
        self.load_current_media()

        # Force redraw
        self.drawing_area.queue_draw()

        # Return False because timeout will be re-scheduled if needed
        return False

    def on_destroy(self, widget):
        print("\nClosing application...")

        # Remove timeouts
        if self.timeout_id:
            GLib.source_remove(self.timeout_id)

        if self.cursor_hide_timeout:
            GLib.source_remove(self.cursor_hide_timeout)

        # Clean up pipeline
        self.cleanup_pipeline()

        Gtk.main_quit()

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Jetson Slideshow')
    parser.add_argument('directory', help='Directory containing images and videos')
    parser.add_argument('--interval', type=int, default=5, help='Seconds to display each image (default: 5)')
    parser.add_argument('--recursive', '-r', action='store_true', help='Search subdirectories recursively')
    parser.add_argument('--shuffle', '-s', action='store_true', help='Shuffle media files randomly')
    args = parser.parse_args()

    # Initialize threading
    GLib.threads_init()
    Gst.init(None)

    viewer = MediaSlideshowViewer(args.directory, args.interval, args.recursive, args.shuffle)

    try:
        Gtk.main()
    except KeyboardInterrupt:
        print("\nInterrupted by user")

if __name__ == "__main__":
    main()
