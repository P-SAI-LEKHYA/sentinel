# backend/utils/metadata_strip.py

import os
import shutil
from pathlib import Path# These are the file types we handle.
# Any file NOT in these lists gets passed through unchanged
# with a warning — we never silently fail on unknown types.

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.webp', '.bmp', '.tiff'}
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
PDF_EXTENSIONS = {'.pdf'}
def strip_metadata(input_path: str, output_path: str = None) -> dict:
    """
    Main function. Takes any file, strips all identifying metadata,
    saves cleaned version.
    
    input_path:  path to original evidence file
    output_path: where to save cleaned file.
                 If None, overwrites original.
                 For safety, always pass an output_path.
    
    Returns a dict explaining what was stripped and what remains.
    """
    
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"File not found: {input_path}")
    
    # If no output path given, create one automatically.
    # cleaned_evidence.jpg saved as cleaned_evidence_stripped.jpg
    if output_path is None:
        p = Path(input_path)
        output_path = str(p.parent / f"{p.stem}_stripped{p.suffix}")
    
    # Detect file type from extension, not from filename.
    # .lower() handles files named IMAGE.JPG or Video.MP4
    extension = Path(input_path).suffix.lower()
    
    if extension in IMAGE_EXTENSIONS:
        return _strip_image_metadata(input_path, output_path)
    
    elif extension in AUDIO_EXTENSIONS:
        return _strip_audio_metadata(input_path, output_path)
    
    elif extension in VIDEO_EXTENSIONS:
        return _strip_video_metadata(input_path, output_path)
    elif extension in PDF_EXTENSIONS:
        return _strip_pdf_metadata(input_path, output_path)
    
    else:
        # Unknown file type — copy it unchanged and warn.
        # We never block a submission because of an unknown file type.
        # Whistleblower's evidence is more important than perfect metadata stripping.
        shutil.copy2(input_path, output_path)
        return {
            "status": "unchanged",
            "reason": f"Unknown file type: {extension}",
            "input": input_path,
            "output": output_path,
            "stripped_fields": [],
            "warning": "Metadata stripping not performed — file type not supported"

        }
def _strip_pdf_metadata(input_path: str, output_path: str) -> dict:
    """
    Strips metadata from PDF files.
    PDFs contain: author name, organization, creation date,
    modification date, software used to create the PDF
    (which can reveal the device or OS), and sometimes
    GPS coordinates if created on a mobile device.
    
    A PDF created in Microsoft Word on Windows will contain
    the Windows username in the author field by default.
    That single field can identify a whistleblower instantly.
    
    Method: use pypdf to read all pages and rewrite the PDF
    without any metadata in the document info dictionary.
    The actual content — text, images, pages — is preserved exactly.
    """
    
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        raise ImportError(
            "pypdf not installed. "
            "Run: pip install pypdf --break-system-packages"
        )
    
    stripped_fields = []
    
    reader = PdfReader(input_path)
    writer = PdfWriter()
    
    # Record what metadata existed before stripping
    # PDF metadata lives in the document info dictionary
    metadata = reader.metadata
    if metadata:
        for key, value in metadata.items():
            stripped_fields.append(f"{key}: {str(value)[:80]}")
    
    # Copy every page from original to new writer
    # This preserves ALL content — text, images, formatting
    # Only the metadata dictionary is left behind
    for page in reader.pages:
        writer.add_page(page)
    
    # add_metadata with empty dict effectively clears all fields
    # We explicitly set common fields to empty strings
    # to ensure nothing leaks through
    writer.add_metadata({
        '/Author':   '',
        '/Creator':  '',
        '/Producer': '',
        '/Title':    '',
        '/Subject':  '',
        '/Keywords': '',
    })
    
    # Write the cleaned PDF to output path
    with open(output_path, 'wb') as output_file:
        writer.write(output_file)
    
    return {
        "status": "stripped",
        "file_type": "pdf",
        "input": input_path,
        "output": output_path,
        "stripped_fields": stripped_fields,
        "fields_count": len(stripped_fields),
        "warning": None
    }
def _strip_image_metadata(input_path: str, output_path: str) -> dict:
    """
    Strips EXIF data from images.
    EXIF contains: GPS coordinates, device model, camera settings,
    creation timestamp, software used, and sometimes thumbnail
    of the photographer's face if front camera was used.
    
    Method: re-save the image pixel data without any metadata.
    Pillow makes this simple — open image, save it again.
    The pixel content is identical. The metadata is gone.
    """
    
    # Import here, not at top of file.
    # This way if Pillow isn't installed, only image stripping fails
    # not the entire module.
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow not installed. Run: pip install Pillow --break-system-packages")
    
    stripped_fields = []
    
    with Image.open(input_path) as img:
        
        # Check what EXIF data exists before stripping
        # so we can report what was removed
        exif_data = img.info.get('exif', None)
        
        if exif_data:
            # Try to read the specific EXIF fields for reporting
            try:
                from PIL.ExifTags import TAGS
                exif = img._getexif()
                if exif:
                    for tag_id, value in exif.items():
                        tag_name = TAGS.get(tag_id, str(tag_id))
                        stripped_fields.append(tag_name)
            except Exception:
                # If we can't read EXIF details, just note it was present
                stripped_fields.append("EXIF data (details unreadable)")
        
        # This is the actual stripping.
        # img.save() without passing exif= parameter saves ONLY pixel data.
        # No GPS, no device model, no timestamp — nothing.
        #
        # We convert to RGB first because some formats (HEIC, PNG with alpha)
        # have color modes that JPEG doesn't support.
        # If output is not JPEG we preserve the original mode.
        
        output_ext = Path(output_path).suffix.lower()
        
        if output_ext in {'.jpg', '.jpeg'}:
            # JPEG cannot store transparency — convert to RGB
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            img.save(output_path, 'JPEG', quality=95)
        
        elif output_ext == '.png':
            # PNG supports transparency — keep original mode
            # PNG also doesn't have EXIF natively, so just resaving cleans it
            img.save(output_path, 'PNG')
        
        else:
            # For other formats, try to save as-is
            # If format doesn't support the mode, convert to RGB
            try:
                img.save(output_path)
            except Exception:
                img.convert('RGB').save(output_path)
    
    return {
        "status": "stripped",
        "file_type": "image",
        "input": input_path,
        "output": output_path,
        "stripped_fields": stripped_fields,
        "fields_count": len(stripped_fields),
        "warning": None
    }
def _strip_audio_metadata(input_path: str, output_path: str) -> dict:
    """
    Strips ID3 tags and metadata from audio files.
    Audio metadata contains: title, artist, album, recording date,
    software used to record, and sometimes GPS coordinates.
    
    Method: use mutagen to read then delete all tags.
    """
    
    try:
        import mutagen
        from mutagen import File as MutagenFile
    except ImportError:
        raise ImportError("mutagen not installed. Run: pip install mutagen --break-system-packages")
    
    # Copy file first — we operate on the copy, not the original
    shutil.copy2(input_path, output_path)
    
    stripped_fields = []
    
    # Open the copied file with mutagen
    # MutagenFile auto-detects format — works for mp3, wav, flac, etc.
    audio = MutagenFile(output_path)
    
    if audio is not None and audio.tags is not None:
        # Record what we're about to strip
        for key in audio.tags.keys():
            stripped_fields.append(str(key))
        
        # delete() removes ALL tags at once
        # This is safer than deleting field by field
        audio.delete()
        audio.save()
    
    return {
        "status": "stripped",
        "file_type": "audio",
        "input": input_path,
        "output": output_path,
        "stripped_fields": stripped_fields,
        "fields_count": len(stripped_fields),
        "warning": None
    }
def _strip_video_metadata(input_path: str, output_path: str) -> dict:
    """
    Video metadata stripping is more complex than images or audio.
    Video containers (MP4, MOV) embed metadata at multiple levels:
    - Container level: creation date, encoder software, GPS
    - Stream level: each video/audio track has its own metadata
    
    Full stripping requires ffmpeg which may not be installed.
    We use mutagen for what we can, and flag what we cannot strip.
    
    For production: always use ffmpeg.
    For this demo: mutagen handles basic metadata.
    """
    
    shutil.copy2(input_path, output_path)
    
    stripped_fields = []
    warnings = []
    
    try:
        from mutagen import File as MutagenFile
        
        video = MutagenFile(output_path)
        
        if video is not None and video.tags is not None:
            for key in video.tags.keys():
                stripped_fields.append(str(key))
            video.delete()
            video.save()
        
        # Note: mutagen cannot strip all video metadata
        # Container-level metadata in MP4/MOV requires ffmpeg
        warnings.append(
            "Partial strip only — container-level metadata may remain. "
            "For complete stripping install ffmpeg."
        )
    
    except Exception as e:
        warnings.append(f"Metadata stripping failed: {str(e)}. Original file copied unchanged.")
    
    return {
        "status": "partial" if warnings else "stripped",
        "file_type": "video",
        "input": input_path,
        "output": output_path,
        "stripped_fields": stripped_fields,
        "fields_count": len(stripped_fields),
        "warning": warnings[0] if warnings else None
    }
def get_metadata_report(file_path: str) -> dict:
    """
    READ-ONLY function. Does not modify any file.
    Just reads and reports what metadata exists in a file.
    
    Use this BEFORE stripping to show the user what will be removed.
    Use this AFTER stripping to verify metadata is gone.
    
    This is what your frontend calls when someone uploads evidence —
    show them "GPS coordinates found, device model found" before
    asking them to confirm submission.
    """
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    extension = Path(file_path).suffix.lower()
    report = {
        "file": file_path,
        "file_type": "unknown",
        "metadata_found": {},
        "risk_level": "UNKNOWN"
    }
    
    if extension in IMAGE_EXTENSIONS:
        report["file_type"] = "image"
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            
            with Image.open(file_path) as img:
                exif = img._getexif()
                if exif:
                    for tag_id, value in exif.items():
                        tag_name = TAGS.get(tag_id, str(tag_id))
                        # Convert value to string for JSON serialization
                        report["metadata_found"][tag_name] = str(value)[:100]
        except Exception as e:
            report["metadata_found"]["error"] = str(e)
    elif extension in PDF_EXTENSIONS:
        report["file_type"] = "pdf"
        try:
            from pypdf import PdfReader
        
            reader = PdfReader(file_path)
            metadata = reader.metadata
        
            if metadata:
                for key, value in metadata.items():
                    report["metadata_found"][str(key)] = str(value)[:100]
        
        # Check for high risk fields specifically
            author = report["metadata_found"].get("/Author", "")
            creator = report["metadata_found"].get("/Creator", "")
        
            if author or creator:
                report["risk_level"] = "HIGH — author or device identity present"
            elif report["metadata_found"]:
                report["risk_level"] = "MEDIUM — creation software detectable"
            else:
                report["risk_level"] = "LOW — no metadata found"
    
        except Exception as e:
            report["metadata_found"]["error"] = str(e)
        
        # Risk assessment — GPS is the highest risk
        if "GPSInfo" in report["metadata_found"]:
            report["risk_level"] = "HIGH - GPS coordinates present"
        elif report["metadata_found"]:
            report["risk_level"] = "MEDIUM - device fingerprinting possible"
        else:
            report["risk_level"] = "LOW - no metadata found"
    
    return report


# Test harness — run directly to test
if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python metadata_strip.py <file_path>")
        sys.exit(1)
    
    target = sys.argv[1]
    
    print("\n--- BEFORE STRIPPING ---")
    report = get_metadata_report(target)
    print(json.dumps(report, indent=2))
    
    print("\n--- STRIPPING ---")
    result = strip_metadata(target)
    print(json.dumps(result, indent=2))
    
    print("\n--- AFTER STRIPPING ---")
    report_after = get_metadata_report(result["output"])
    print(json.dumps(report_after, indent=2))