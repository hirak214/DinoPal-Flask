from flask import Flask, render_template, request, redirect
import requests

from config import JSON_DATA_FISCHER, JSON_DATA_MICROSPEC, API_URL
import json
import random


app = Flask(__name__)

ACCESS_FLAGS = [False, False, False]
@app.route("/")
def home():
    ACCESS_FLAGS[0] = True
    print(ACCESS_FLAGS)
    return render_template("home.html", res_data={'data':['Lesgo']}, put_data={'data':['Lesgo']})

# function to get and send data to the table from the api
@app.route("/get_data", methods=["POST"])
def get_data():
    if ACCESS_FLAGS[0] == True:
        ACCESS_FLAGS[1] = True
        # check if method is post
        if request.method == "POST":
            # convert data from form to dictionary
            data = request.form.to_dict()
            print(f"data: {data}")
            # check if not data has any null values
            if not is_dict_empty(data):
                # check which machine is to be used
                if data["machine"] == "machine1": machine_data = JSON_DATA_MICROSPEC
                elif data["machine"] == "machine2": machine_data = JSON_DATA_FISCHER
                else: return {'status': False, 'message': 'Selected Machine does not exist', 'data': None}
                # get data from api
                res_data_from_server = get_data_from_server(data['request_num'], data['job_num'], machine_data)
                # res_data_from_server = get_local_data()
                # if valid data returned
                if res_data_from_server['status'] == True:
                    # csching the data
                    res_cache = put_cache("get_data.json", res_data_from_server['data'])
                    if res_cache['status']:
                        res_cache = put_cache("job_data.json", data)
                        if res_cache['status']:

                            # extracting data from res
                            res_data = res_data_from_server
                            res_data['status'] = "Data Received"  # set status as data received
                            res_data['length_data'] = len(res_data['data'])  # set length of data
                            res_data['data'] = res_data['data']  # set data to first 5 rows
                            return render_template("home.html", res_data=res_data, put_data={'data':['Lesgo']})
                        else:
                            return res_cache
                    else:
                        return res_cache
                else:
                    return res_data_from_server
            else:
                return render_template("home.html")
    else:
        return {'status': False, 'message': 'Access Denied, Button is disabled', 'data': None}



def get_data_from_server(request_number, job_number, machine_data):
    try:
        get_url = API_URL + f"reqno={request_number}&jobno={job_number}"
        res = requests.get(get_url, json=machine_data)
        if res.status_code == 200:
            if res.json()[0] != {'Error': 'No data found !! Please Check Your Job no and Req No '}:
                return {'status': True, 'message': "Data fetched sucessfuly", 'data': res.json()}
            else:
                return {'status': False, 'message': "Data Does not Exist", 'data': None}
        else:
            return {'status': False, 'message': f"Got status code {res.status_code}", 'data': None}
    except Exception as e:
        return {'status': False, 'message': e, 'data': e}


def is_dict_empty(d):
    try:
        for value in d.values():
            if value != "":
                return False
        return True
    except Exception as e:
        return {'status': False, 'message': "Error in is_dict_empty", 'data': e}

# function to get and send data to the table from the api
@app.route("/generate_data", methods=["POST"])
def generate_data():
    try:
        if ACCESS_FLAGS[1] == True:
            ACCESS_FLAGS[2] = True
            if request.method == "POST":
                data = request.form.to_dict()
                get_result = get_cache("get_data.json")
                if get_result['status']:
                    res_data = {'status': True, 'message': "Data re-fetched sucessfuly", 'data': get_result['data']}
                    res_data['length_data'] = len(res_data['data'])  # set length of data
                    send_data = generate_xrf_reading(get_result['data'])
                    if send_data['status']:
                        put_result = put_cache("put_data.json", send_data['data'])
                        if put_result['status']:
                            send_data['generated_readings'] = len(send_data['data'])
                            return render_template("home.html", res_data=res_data, put_data=send_data)
                        else:
                            return put_result
                else:
                    return get_result
            else:
                return {'status': False, 'message': "Please use POST method", 'data': None}
        else:
            return {'status': False, 'message': "Access Denied, button is disabled", 'data': None}
    except Exception as e:
        return {'status': False, 'message': "Error in generate_data", 'data': e}

def generate_xrf_reading(get_result):
    try:
        len_get_result_start = len(get_result)
        send_data = []
        for i, res in enumerate(get_result):
            for j in range(1, 100, 98):
                send_temp = res.copy()
                purity = send_temp['declare_purity'][:2]
                metal_values = generate_metal_values(purity)

                send_temp['gold'] = metal_values['au']
                send_temp['silver'] = metal_values['ag']
                send_temp['copper'] = metal_values['cu']

                send_temp['reading'] = f"{j}"
                send_temp.pop('date')
                send_temp['declare_purity'] = send_temp['declare_purity'][3:]
                send_data.append(send_temp)
        if len(send_data) == len_get_result_start * 2:
            return {'status': True, 'message': "Data generated sucessfuly", 'data': send_data}
        else:
            return {'status': False, 'message': "Error in generate_xrf_reading, not 2 readings generated for all", 'data': 
            None}
    except Exception as e:
        return {'status': False, 'message': "Error in generate_xrf_reading", 'data': e}

def generate_metal_values(purity):
    values = {}
    while True:
        values['au'] = round(random.uniform(916.90, 918.90), 3)
        values['ag'] = round(random.uniform(12.5, 20.0), 3)
        values['zn'] = round(random.uniform(6, 7), 3)
        values['cu'] = round(1000 - values['au'] - values['ag'] - values['zn'], 3)
        if (values['au'] + values['ag'] + values['cu'] + values['zn']) == 1000:
            return values

@app.route("/send_data", methods=["POST"])
def send_data():
    print("Entering send_data")
    try:
        if ACCESS_FLAGS[2] == True:
            if request.method == "POST":
                res_job_data = get_cache("job_data.json")
                if res_job_data['status']:
                    job_data = res_job_data['data']
                    res_final_xrf_data = get_cache("put_data.json")
                    if res_final_xrf_data['status']:
                        final_xrf_data = res_final_xrf_data['data']
                        # check which machine is to be used
                        if job_data["machine"] == "machine1": machine_data = JSON_DATA_MICROSPEC
                        elif job_data["machine"] == "machine2": machine_data = JSON_DATA_FISCHER
                        send_data = make_api_call(job_data['request_num'], job_data['job_num'], machine_data, final_xrf_data)
                        if send_data['status']:
                            print("setting flags to false")
                            ACCESS_FLAGS[1] = ACCESS_FLAGS[2] = False
                            print(f"send_data['data'] = {send_data['data']}")
                            print(f"Access flags = {ACCESS_FLAGS}")
                            return render_template("home.html", res_data=send_data['data'][0])
                        else:
                            return send_data
                    else:
                        return res_final_xrf_data

    except Exception as e:
        return {'status': False, 'message': "Error in send_data", 'data': e}

def make_api_call(request_number, job_number, machine_data, final_xrf_data):
    try:
        if ACCESS_FLAGS[2] == True:
            # postxrfJobdetails
            post_url = API_URL + f"reqno={request_number}&jobno={job_number}"
            res = requests.get(post_url, json=machine_data)
            # postxrfJobdetails
            POST_URL = f"https://huid.manakonline.in/MANAK/getxrfJobdetails?reqno={request_number}&jobno={job_number}"

            machine_data['xrfdetail'] = final_xrf_data

            res = requests.post(POST_URL, json=machine_data)
            if res.status_code == 200:
                print("Data sent sucessfuly")
                return {'status': True, 'message': "Data sent sucessfuly", 'data': res.json()}
            else:
                return {'status': False, 'message': "Error in send_data, status code not 200", 'data': res.json()}
        else:
            return {'status': False, 'message': "Access Denied, button is disabled", 'data': None}
    except Exception as e:
        return {'status': False, 'message': "Error in send_data", 'data': e}

def put_cache(filename, data):
    try:
        with open(filename, 'w') as f:
            json.dump(data, f)
        return {'status': True, 'message': "Data put in cache sucessfuly", 'data': None}
    except Exception as e:
        return {'status': False, 'message': "Error in put_cache", 'data': e}

def get_cache(filename):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        return {'status': True, 'message': "Data fetched from cache sucessfuly", 'data': data}
    except Exception as e:
        return {'status': False, 'message': "Error in get_cache", 'data': e}


if __name__ == "__main__":
    app.run(debug=True, port=5003)


