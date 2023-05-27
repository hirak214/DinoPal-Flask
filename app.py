from flask import Flask, render_template, request, redirect
import requests

from config import JSON_DATA_FISCHER, JSON_DATA_MICROSPEC, API_URL
import json
import random
import csv
import os
import pathlib
from datetime import datetime
import logging



app_log_path = os.path.join(os.getcwd(), 'logs', 'app.log')
logging.basicConfig(filename=app_log_path, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('app.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("home.html", res_data={'data':['Lesgo']}, put_data={'data':['Lesgo']})

# function to get and send data to the table from the api
@app.route("/get_data", methods=["POST"])
def get_data():
    # check if method is post
    if request.method == "POST":
        # convert data from form to dictionary
        data = request.form.to_dict()
        # check if not data has any null values
        if not is_dict_empty(data):
            # check which machine is to be used
            if data["machine"] == "machine1": machine_data = JSON_DATA_MICROSPEC
            elif data["machine"] == "machine2": machine_data = JSON_DATA_FISCHER
            else: return {'status': False, 'message': 'Selected Machine does not exist', 'data': None}
            # get data from api
            res_data_from_server = get_data_from_server(data['request_num'], data['job_num'], machine_data)
            logging.info(f'got data from {machine_data} of request number {data["request_num"]} and job number {data["job_num"]} ')
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
                        logging.error(f'Error in putting data in job_data.json, {res_cache["message"]}')
                        return res_cache
                else:
                    logging.error(f'Error in putting data in get_data.json, {res_cache["message"]}')
                    return res_cache
            else:
                logging.error(f'Error in getting data from server, {res_data_from_server["message"]}')
                return res_data_from_server
        else:
            return render_template("home.html") 



def get_data_from_server(request_number, job_number, machine_data):
    try:
        get_url = API_URL + f"reqno={request_number}&jobno={job_number}"
        res = requests.get(get_url, json=machine_data)
        if res.status_code == 200:
            if res.json()[0] != {'Error': 'No data found !! Please Check Your Job no and Req No '}:
                return {'status': True, 'message': "Data fetched sucessfuly", 'data': res.json()}
            else:
                logging.error(f'Error in getting data from server, {res.json()}')
                return {'status': False, 'message': "Data Does not Exist", 'data': None}
        else:
            logging.error(f'Error in getting data from server, {res.status_code}')
            return {'status': False, 'message': f"Got status code {res.status_code}", 'data': None}
    except Exception as e:
        logging.error(f'Error in getting data from server, {e}')
        return {'status': False, 'message': e, 'data': e}


def is_dict_empty(d):
    try:
        for value in d.values():
            if value != "":
                return False
        return True
    except Exception as e:
        logging.error(f'Error in is_dict_empty, {e}')
        return {'status': False, 'message': "Error in is_dict_empty", 'data': e}

# function to get and send data to the table from the api
@app.route("/generate_data", methods=["POST"])
def generate_data():
    try:
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
                        return render_template("home.html", res_data=send_data, put_data=send_data)
                    else:
                        logging.error(f'Error in putting data in put_data.json, {put_result["message"]}')
                        return put_result
            else:
                logging.error(f'Error in getting data from get_data.json, {get_result["message"]}')
                return get_result
        else:
            logging.error(f'Error in generate_data, Please use POST method')
            return {'status': False, 'message': "Please use POST method", 'data': None}
    except Exception as e:
        logging.error(f'Error in generate_data, {e}')
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
            logging.error(f'Error in generate_xrf_reading, not 2 readings generated for all')
            return {'status': False, 'message': "Error in generate_xrf_reading, not 2 readings generated for all", 'data': 
            None}
    except Exception as e:
        logging.error(f'Error in generate_xrf_reading, {e}')
        return {'status': False, 'message': "Error in generate_xrf_reading", 'data': e}

def generate_metal_values(purity):
    values = {}
    if purity == str(22):
        while True:
            values['au'] = round(random.uniform(916.90, 918.90), 3)
            values['ag'] = round(random.uniform(12.5, 20.0), 3)
            values['zn'] = round(random.uniform(6, 7), 3)
            values['cu'] = round(1000 - values['au'] - values['ag'] - values['zn'], 3)
            if (values['au'] + values['ag'] + values['cu'] + values['zn']) == 1000:
                return values
    elif purity == str(18):
        while True:
            values['au'] = round(random.uniform(750.5, 755.0), 3)
            values['ag'] = round(random.uniform(12.5, 20.0), 3)
            values['zn'] = round(random.uniform(6, 7), 3)
            values['cu'] = round(1000 - values['au'] - values['ag'] - values['zn'], 3)
            if (values['au'] + values['ag'] + values['cu'] + values['zn']) == 1000:
                return values
    else:
        logging.error(f'Error in generate_metal_values, purity not 18 or 22')
        return {'status': False, 'message': "Error in generate_metal_values, purity not 18 or 22", 'data': None}

def generate_filenames(jobid):
    file_path = os.join(os.getcwd(), 'xrfcsv', f'{jobid}.csv')
    return file_path

def reorder_dict(dictionary, fieldnames):
    return {key: dictionary[key] for key in fieldnames}

def log_dicts_to_csv(data, jobid, reqno, machine):
    filename = generate_filenames(jobid)
    fieldnames = ['tag_id', 'declare_purity', 'reading', 'gold', 'copper', 'silver', 'cadmium', 'iridium',
                  'nickel', 'osmium', 'platinum', 'palladium', 'rhodium', 'ruthenium']
    file_exists = os.path.isfile(filename)

    with open(filename, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()  # Write the header row if the file is newly created

        for d in data:
            reordered_dict = reorder_dict(d, fieldnames)
            writer.writerow(reordered_dict)  # Write each reordered dictionary as a row in the CSV file

    with open(filename, "a", newline='') as file:
        csvwrite = csv.writer(file)
        jobid = f"Job Id: {jobid}"
        reqno = f"Req No: {reqno}"
        count = f"Number of pieces: {len(data)/2}"
        today = datetime.today()
        date = f"{today.day}/{today.month}/{today.year}"
        donedate = f"Completion Date: {date}"
        machine = f"Machine: {machine}"
        data = [jobid, reqno, count, donedate, machine]
        csvwrite.writerow(data)
    


@app.route("/send_data", methods=["POST"])
def send_data():
    try:
        if request.method == "POST":
            res_job_data = get_cache("job_data.json")
            if res_job_data['status']:
                job_data = res_job_data['data']
                res_final_xrf_data = get_cache("put_data.json")
                if res_final_xrf_data['status']:
                    final_xrf_data = res_final_xrf_data['data']
                    # check which machine is to be used
                    if job_data["machine"] == "machine1":
                        machine_data = JSON_DATA_MICROSPEC
                        machine_name = "MICROSPEC"
                    elif job_data["machine"] == "machine2":
                        machine_data = JSON_DATA_FISCHER
                        machine_name = "FISCHER"
                    send_data = make_api_call(job_data['request_num'], job_data['job_num'], machine_data, final_xrf_data)
                    if send_data['status']:
                        log_dicts_to_csv(final_xrf_data, job_data['job_num'], job_data['request_num'], machine_name)
                        clear_cache_file("job_data.json")
                        clear_cache_file("put_data.json")
                        clear_cache_file("get_result.json")
                        logging.info(f'Job {job_data["job_num"]} completed successfully from {machine_name}')
                        return render_template("home.html", res_data={'data':['Complete']}, put_data={'data':['completed']})
                    else:
                        logging.error(f'Error in send_data, {send_data}')
                        return send_data
                else:
                    logging.error(f'Error in send_data, {res_final_xrf_data}')
                    return res_final_xrf_data
    except Exception as e:
        logging.error(f'Error in send_data, {e}')
        return {'status': False, 'message': "Error in send_data", 'data': e}

def make_api_call(request_number, job_number, machine_data, final_xrf_data):
    try:
        # postxrfJobdetails
        post_url = API_URL + f"reqno={request_number}&jobno={job_number}"
        res = requests.get(post_url, json=machine_data)
        # postxrfJobdetails
        POST_URL = f"https://huid.manakonline.in/MANAK/getxrfJobdetails?reqno={request_number}&jobno={job_number}"

        machine_data['xrfdetail'] = final_xrf_data

        res = requests.post(POST_URL, json=machine_data)
        if res.status_code == 200:
            return {'status': True, 'message': "Data sent sucessfuly", 'data': res.json()}
        else:
            logging.error(f'Error in send_data, status code not 200, {res.json()}')
            return {'status': False, 'message': "Error in send_data, status code not 200", 'data': res.json()}
    except Exception as e:
        logging.error(f'Error in send_data, {e}')
        return {'status': False, 'message': "Error in send_data", 'data': e}

def put_cache(filename, data):
    try:
        with open(filename, 'w') as f:
            json.dump(data, f)
        return {'status': True, 'message': "Data put in cache sucessfuly", 'data': None}
    except Exception as e:   
        logging.error(f'Error in put_cache, {e}')
        return {'status': False, 'message': "Error in put_cache", 'data': e}

def get_cache(filename):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        return {'status': True, 'message': "Data fetched from cache sucessfuly", 'data': data}
    except Exception as e:
        logging.error(f'Error in get_cache, {e}')
        return {'status': False, 'message': "Error in get_cache", 'data': e}

def clear_cache_file(filename):
    # Open the file in write mode and overwrite it with an empty JSON object
    with open(filename, 'w') as file:
        json.dump({}, file)

if __name__ == "__main__":
    app.run(debug=True, port=5003)


