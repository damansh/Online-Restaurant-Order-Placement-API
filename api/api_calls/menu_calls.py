from flask import Flask, Blueprint, request, jsonify
from flask_api import status
from aws_clients import restaurantS3Bucket, s3Client, s3Resource, MenuDatabase
import os

# Define blueprint for Flask
menu_calls = Blueprint('menu_calls', __name__)

def isCostInDollars(itemCost, validCurrencies="$"):
    return any(c in itemCost for c in validCurrencies)

def addItemToMenu(itemName, itemCost):
    cost = itemCost.replace('$', '')

    response = MenuDatabase.put_item(
        Item = {
            'item': itemName,
            'cost': cost,
            'status': 'available'
        }
    )

    return "Successfully added item '" + itemName + "' to the menu"

def updateImageInS3(imageName, uploadedFile):
    fileName, fileExtension = os.path.splitext(uploadedFile.filename)
    newFileName = imageName + fileExtension

    uploadedFile.seek(0)
    s3Client.upload_fileobj(uploadedFile, restaurantS3Bucket, newFileName)            

    s3Resource.Object(restaurantS3Bucket, newFileName).wait_until_exists()

    return "Successfully updated the image of item '" + imageName + "' in the S3 bucket"

@menu_calls.route('/menu', methods=['PUT'])
def add_to_menu():
    requestData = request.form
    response = {}

    # Check if the body has the item and cost
    if not requestData or 'item' not in requestData or 'cost' not in requestData:
        response["error"] = 'Include item and cost attributes in the request'
        return jsonify(response), status.HTTP_400_BAD_REQUEST

    itemName = requestData['item']
    itemCost = requestData['cost']

    # Check if the cost is valid
    if not isCostInDollars(itemCost):
        response["error"] = 'The item currency is valid. Only $ is supported'
        return jsonify(response), status.HTTP_400_BAD_REQUEST

    # Check if an image is already in the S3 bucket. If there is, then continue to use that image. 
    # Otherwise, use the image uploaded by the restaurant.
    results = s3Client.list_objects(Bucket=restaurantS3Bucket, Prefix=itemName)

    # There is no existing image and a file has not been uploaded. Throw an error
    if 'Contents' not in results and 'file' not in request.files:
        response["error"] = 'There is no existing image in the menu database and an image has not been attached to the request'
        return jsonify(response), status.HTTP_400_BAD_REQUEST

    response['item'] = itemName
    response['cost'] = itemCost
    
    response['database_status'] = addItemToMenu(itemName, itemCost)

    if 'file' in request.files:
        response['image_database_status'] = updateImageInS3(itemName, request.files['file'])

    return response
