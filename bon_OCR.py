#import easyocr
import os
import math
from typing import Tuple, Union

import cv2
import numpy as np

from deskew import determine_skew

import pytesseract as pytess
print(os.getcwd())

# roteet
def rotate(image: np.ndarray, angle: float, background: Union[int, Tuple[int, int, int]]) -> np.ndarray:
    old_width, old_height = image.shape[:2]
    angle_radian = math.radians(angle)
    width = abs(np.sin(angle_radian) * old_height) + abs(np.cos(angle_radian) * old_width)
    height = abs(np.sin(angle_radian) * old_width) + abs(np.cos(angle_radian) * old_height)

    image_center = tuple(np.array(image.shape[1::-1]) / 2)
    rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
    rot_mat[1, 2] += (width - old_width) / 2
    rot_mat[0, 2] += (height - old_height) / 2
    return cv2.warpAffine(image, rot_mat, (int(round(height)), int(round(width))), borderValue=background)


# noise removal
def remove_noise(image):
    return cv2.medianBlur(image,5)


# Picture in variable
image = cv2.imread('test_data/ah_5_cropped.jpg')
#noise removal
image = remove_noise(image)
# Make grayscale of picture
grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
# Determine angle of skew
angle = determine_skew(grayscale) + 90
# Rotate the grayscaled image based on angle
rotated = rotate(grayscale, angle, (0, 0, 0))
image = rotated
# Threshold image
image = cv2.threshold(image, 150 ,255,cv2.THRESH_BINARY)[1]

# Write new image to new file
cv2.imwrite('test_data/output.jpg', image)

#reader = easyocr.Reader(['nl',]) # need to run only once to load model into memory
#result = reader.readtext(image, paragraph=False, detail=0)
#print(result)
#https://github.com/JaidedAI/EasyOCR

bon_out = pytess.image_to_data(image, lang="nld", output_type=pytess.Output.DATAFRAME)
#print(bon_out)

# disable dicts: https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html#dictionaries-word-lists-and-patterns
data = bon_out[["page_num", "block_num", "par_num", "line_num", "word_num", "conf", "text", "left", "width", "top", "height"]]
data = data[data["conf"] > 0]