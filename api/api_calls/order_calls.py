from flask import Flask, Blueprint, request, jsonify
from flask_api import status
from aws_clients import restaurantS3Bucket, s3Client, s3Resource, OrderDatabase, MenuDatabase
from boto3.dynamodb.conditions import Attr
from decimal import Decimal
import os
import uuid

# Define blueprint for Flask
order_calls = Blueprint('order_calls', __name__)

@order_calls.route('/order', methods=['POST'])
def place_order():
    requestData = request.form
    response = {}

    # Check if the body has the item and cost
    if not requestData or 'food' not in requestData:
        response["error"] = 'Include the food that you want to order in the request'
        return jsonify(response), status.HTTP_400_BAD_REQUEST

    foodToOrder = requestData.getlist('food')

    orderedItems = []
    finalPrice = 0
    for food in foodToOrder:
        foodItem, quantity = food.split(",")
        quantity = int(quantity)

        responseDDB = MenuDatabase.scan(
            FilterExpression = Attr('item').contains(foodItem) & Attr('status').eq('available')
        )

        menuItem = responseDDB['Items']

        if not menuItem:
            response["error"] = "Item '" + foodItem + "' is not available for order. Cancelling order. Send another order request"
            return jsonify(response), status.HTTP_400_BAD_REQUEST
        
        if len(menuItem) > 1:
            response["error"] = "There are multiple items with the search keyword '" + foodItem + "':  " + [item['item'] for item in menuItem]
            response["error"] += " Please refine your order and send another order request"
            return jsonify(response), status.HTTP_400_BAD_REQUEST

        orderedItem = {}
        orderedItem['item'] = menuItem[0]['item']
        orderedItem['quantity'] = quantity
        orderedItem['cost'] = '${:,.2f}'.format(quantity * menuItem[0]['cost'])
        
        finalPrice += quantity * menuItem[0]['cost']
        orderedItems.append(orderedItem)
    
    response['order_id'] = str(uuid.uuid4())
    response['ordered_items'] = orderedItems
    response['final_price'] = '${:,.2f}'.format(finalPrice)

    responseDDB = OrderDatabase.put_item(
        Item = {
            'order_id': response['order_id'],
            'items': orderedItems,
            'final_price': finalPrice,
            'status': 'received'
        }
    )

    return response
