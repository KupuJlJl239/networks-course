import json
from flask import Flask, abort, request, send_file
from copy import deepcopy
from werkzeug.datastructures import FileStorage
import io


id2data: dict = {}  # {0: {'name': 'product1', 'description': 'fhauionyufdsa'}}
name_to_file: dict = {}


def find_free_id() -> int:
	id = 0
	while id in id2data.keys():
		id += 1
	return id
	
	
def add_product(data: dict) -> int:
	id = find_free_id()
	id2data[id] = data
	return id


def update_product(id: int, new_data: dict):
	for k, v in new_data.items():
		id2data[id][k] = v


def get_product_with_id(id: int) -> dict:
	res = deepcopy(id2data[id])
	res['id'] = id
	return res


app = Flask(__name__)


# 1
@app.route('/product', methods=['POST'])
def r_add_product():
	data = request.get_json()
	id = add_product(data)
	return get_product_with_id(id)


# 2
@app.route('/product/<int:id>', methods=['GET'])
def r_get_product_by_id(id: int):
	if id not in id2data.keys():
		abort(404)
	return get_product_with_id(id)


# 3
@app.route('/product/<int:id>', methods=['PUT'])
def r_update_product_by_id(id: int):
	if id not in id2data.keys():
		abort(404)
	data = request.get_json()
	update_product(id, data)
	return get_product_with_id(id)


# 4
@app.route('/product/<int:id>', methods=['DELETE'])
def r_delete_product_by_id(id: int):
	if id not in id2data.keys():
		abort(404)
	res = deepcopy(get_product_with_id(id))
	id2data.pop(id)
	return res


# 5
@app.route('/products', methods=['GET'])
def r_get_list_of_all_products():
	return [get_product_with_id(id) for id in id2data.keys()]


# 6
@app.route('/product/<int:id>/image', methods=['POST'])
def r_post_image(id: int):
	assert len(request.files) == 1

	icon, file_storage = next(iter(request.files.items()))
	assert icon == 'icon'

	file_name = file_storage.filename
	file_storage.save(file_name)
	id2data[id]['icon'] = file_name
	return get_product_with_id(id)


# 7
@app.route('/product/<int:id>/image', methods=['GET'])
def r_get_image(id: int):
	file_name = id2data[id]['icon']
	return send_file(file_name)




