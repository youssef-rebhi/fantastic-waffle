def capture_and_process_image(rect):
    """Capture screenshot and process for better OCR"""
    # Capture screenshot
    screenshot = pyautogui.screenshot(region=rect)
    
    # Convert to OpenCV format for preprocessing
    img_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    
    # Preprocess image
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Convert back to PIL for OCR
    processed_img = Image.fromarray(thresh)
    
    # OCR configuration optimized for text and numbers
    config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,()[]{}:;!?-_ '
    
    # Extract text
    text = pytesseract.image_to_string(processed_img, config=config)
    return text.strip()

def parse_options(text):
    """Parse options text and clean up formatting"""
    lines = text.split('\n')
    options = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Remove common option prefixes
        cleaned = line
        # Remove letter prefixes (A), B), C), D))
        if (cleaned and cleaned[0] in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' and 
            len(cleaned) > 1 and cleaned[1] in ').'):
            cleaned = cleaned[2:].strip()
        # Remove number prefixes (1., 2., 3., etc.)
        elif (cleaned and cleaned[0].isdigit() and 
              len(cleaned) > 1 and cleaned[1] in '.)'):
            cleaned = cleaned[2:].strip()
        
        if cleaned:
            options.append(cleaned)
    
    return options
