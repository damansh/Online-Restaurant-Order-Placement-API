from flask import Flask, Blueprint, request, jsonify
from flask_api import status
from aws_clients import restaurantS3Bucket, s3Client, s3Resource, OrderDatabase, MenuDatabase
from boto3.dynamodb.conditions import Attr, Key
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
        orderedItem['quantity'] = str(quantity)
        orderedItem['cost'] = '${:,.2f}'.format(quantity * float(menuItem[0]['cost']))
        
        finalPrice += quantity * menuItem[0]['cost']
        orderedItems.append(orderedItem)
    
    response['order_id'] = str(uuid.uuid4())
    response['ordered_items'] = orderedItems
    response['final_price'] = '${:,.2f}'.format(finalPrice)

    responseDDB = OrderDatabase.put_item(
        Item = {
            'order_id': response['order_id'],
            'items': orderedItems,
            'final_price': response['final_price'],
            'status': 'received'
        }
    )

    return response

@order_calls.route('/order/status', methods=['PUT'])
def modify_order_status():
    requestData = request.form
    response = {}

    # Check if the body has the item and cost
    if not requestData or 'order-id' not in requestData or 'newStatus' not in requestData:
        response["error"] = 'Include the order-id and the newStatus of the order'
        return jsonify(response), status.HTTP_400_BAD_REQUEST
    
    newStatus = requestData['newStatus']
    orderId = requestData['order-id']

    validStatuses = ['received', 'in progress', 'ready']

    if newStatus not in ['received', 'in progress', 'ready']:
        response["error"] = "Status '" + newStatus + "' is invalid. Valid statuses: " + ', '.join(validStatuses)
        return jsonify(response), status.HTTP_400_BAD_REQUEST

    responseDDB = OrderDatabase.query(
        KeyConditionExpression = Key('order_id').eq(orderId)
    )

    if not responseDDB['Items']:
        response["error"] = "Order-id '" + orderId + "' is invalid."
        return jsonify(response), status.HTTP_400_BAD_REQUEST
    
    currentOrder = responseDDB['Items'][0]

    if currentOrder['status'] == newStatus:
        response["message"] = "The status of order '" + orderId + "' is already set to '" + newStatus + "'"
        return jsonify(response)

    OrderDatabase.update_item(
        Key={'order_id': orderId},
        UpdateExpression ="SET #s = :newStatus",                   
        ExpressionAttributeValues={':newStatus': newStatus},
        ExpressionAttributeNames={"#s": "status"}
    )

    response['message'] = "The status of order '" + orderId + "' is now set to '" + newStatus + "'"

    return response

# Populate the API response
def populate_response(responseDDB, response):
    response["orders"] = [order for order in responseDDB['Items']]

def get_all_orders(response):
    responseDDB = OrderDatabase.scan()

    populate_response(responseDDB, response)

def get_specific_order(orderid, response):
    responseDDB = OrderDatabase.scan(
        FilterExpression = Attr('order-id').contains(orderid)
    )
    if not responseDDB['Items']:
        response['error'] = "There is no order with the order-id '" + orderid + "'"
    else:
        populate_response(responseDDB, response)

@order_calls.route('/order', methods=['GET'])
def get_order():
    requestData = request.form
    response = {}

    if 'order-id' in requestData:
        orderid = requestData['order-id']
        get_specific_order(orderid, response)
    else:
        get_all_orders(response)
    print(response)
    return response

@order_calls.route('/order', methods=['DELETE'])
def delete_order():
    requestData = request.form
    response = {}

    # Check if the body has the item and cost
    if not requestData or 'order-id' not in requestData:
        response["error"] = 'Include the order-id of the order to delete'
        return jsonify(response), status.HTTP_400_BAD_REQUEST
    
    orderId = requestData['order-id']

    responseDDB = OrderDatabase.query(
        KeyConditionExpression = Key('order_id').eq(orderId)
    )

    if not responseDDB['Items']:
        response["error"] = "Order-id '" + orderId + "' is invalid."
        return jsonify(response), status.HTTP_400_BAD_REQUEST
    
    currentOrder = responseDDB['Items'][0]

    if currentOrder['status'] != "received":
        response["error"] = "The status of the order is currently '" + currentOrder['status'] + "'. Unable to cancel the order"
        return jsonify(response), status.HTTP_400_BAD_REQUEST

    responseDDB = OrderDatabase.delete_item(
        Key = {
            "order_id": orderId
        }
    )

    response['message'] = "Successfully deleted order with the order-id '" + orderId + "'"

    return response
