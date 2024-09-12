from flask import Flask, render_template, request, redirect
import requests
import json
import random
import csv
import os
import pathlib
from datetime import datetime
import logging
import pandas as pd
from config import JSON_DATA_FISCHER, JSON_DATA_MICROSPEC, API_URL

# Define the log file path
log_dir = os.path.join(os.getcwd(), 'logs')
os.makedirs(log_dir, exist_ok=True)  # Create the logs directory if it doesn't exist
app_log_path = os.path.join(log_dir, 'app.log')

# Configure the logger
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)

# Create a file handler that logs to 'app.log'
file_handler = logging.FileHandler(app_log_path)
file_handler.setLevel(logging.DEBUG)  # Log all levels to the file

# Create a formatter and set it for the handler
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Clear any existing handlers and add the file handler
logger.handlers = []
logger.addHandler(file_handler)

# Suppress default logging to terminal
logging.getLogger().handlers = []

app = Flask(__name__)

@app.route("/")
def home():
    clear_cache_file("job_data.json")
    clear_cache_file("put_data.json")
    clear_cache_file("get_result.json")
    clear_cache_file("get_data.json")
    logger.info("Rendering home page.")
    return render_template("home.html", res_data={'data': 'Ready to use'}, put_data={'data': 'Ready to use'}, message_data={'data': 'Ready to use'})

@app.route("/get_data", methods=["POST"])
def get_data():
    if request.method == "POST":
        data = request.form.to_dict()
        logger.debug(f"Received form data: {data}")

        if data:
            if data["machine"] == "machine1":
                machine_data = JSON_DATA_MICROSPEC
            elif data["machine"] == "machine2":
                machine_data = JSON_DATA_FISCHER
            else:
                logger.warning("Selected Machine does not exist.")
                return {'status': False, 'message': 'Selected Machine does not exist', 'data': None}

            res_data_from_server = get_data_from_server(data['request_num'], data['job_num'], machine_data)
            logger.info(f"Data fetched for request_num {data['request_num']} and job_num {data['job_num']}.")

            if res_data_from_server['status']:
                res_cache = put_cache("get_data.json", res_data_from_server['data'])
                if res_cache['status']:
                    res_cache = put_cache("job_data.json", data)
                    if res_cache['status']:
                        res_data = res_data_from_server
                        res_data['status'] = "Data Received"
                        res_data['length_data'] = len(res_data['data'])
                        return render_template("home.html", res_data=res_data, put_data={'data': None, 'message': 'Data Received'}, message_data={'data': 'Data Received'})
                    else:
                        logger.error(f"Error in putting data in job_data.json: {res_cache['message']}")
                        return res_cache
                else:
                    logger.error(f"Error in putting data in get_data.json: {res_cache['message']}")
                    return res_cache
            else:
                logger.error(f"Error in getting data from server: {res_data_from_server['message']}")
                return res_data_from_server
        else:
            logger.warning("Form data contains null values.")
            return render_template("home.html")

def get_data_from_server(request_number, job_number, machine_data):
    try:
        get_url = API_URL + f"reqno={request_number}&jobno={job_number}"
        logger.debug(f"Making API request to: {get_url} with data: {machine_data}")
        res = requests.get(get_url, json=machine_data)

        if res.status_code == 200:
            if res.json()[0] != {'Error': 'No data found !! Please Check Your Job no and Req No '}:
                logger.info("Data fetched successfully from API.")
                return {'status': True, 'message': "Data fetched successfully", 'data': res.json()}
            else:
                logger.warning(f"No data found for the provided request number and job number.")
                return {'status': False, 'message': "Data Does not Exist", 'data': None}
        else:
            logger.error(f"API request returned status code {res.status_code}: {res.text}")
            return {'status': False, 'message': f"Got status code {res.status_code}", 'data': None}
    except Exception as e:
        logger.exception(f"Exception occurred while fetching data from server: {str(e)}")
        return {'status': False, 'message': str(e), 'data': None}


@app.route("/generate_data", methods=["POST"])
def generate_data():
    try:
        if request.method == "POST":
            data = request.form.to_dict()
            logger.debug(f"Received data for generating: {data}")

            get_result = get_cache("get_data.json")
            if get_result['status']:
                res_data = {'status': True, 'message': "Data re-fetched successfully", 'data': get_result['data']}
                res_data['length_data'] = len(res_data['data'])

                generate_data_res = generate_xrf_reading(get_result['data'])
                if generate_data_res['status']:
                    put_result = put_cache("put_data.json", generate_data_res['data'])
                    if put_result['status']:
                        generate_data_res['generated_readings'] = len(generate_data_res['data'])
                        logger.info("Data generated and saved successfully.")
                        return render_template("home.html", res_data=res_data, put_data=generate_data_res, message_data={'data': 'Data Generated'})
                    else:
                        logger.error(f"Error in putting data in put_data.json: {put_result['message']}")
                        return put_result
            else:
                logger.error(f"Error in getting data from cache: {get_result['message']}")
                return get_result
        else:
            logger.warning("Method used is not POST for generating data.")
            return {'status': False, 'message': "Please use POST method", 'data': None}
    except Exception as e:
        logger.exception(f"Exception in generate_data: {str(e)}")
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
                send_temp['declare_purity'] = send_temp['declare_purity'].strip()[-3:]
                send_data.append(send_temp)
        if len(send_data) == len_get_result_start * 2:
            logger.info("XRF readings generated successfully.")
            return {'status': True, 'message': "Data generated successfully", 'data': send_data}
        else:
            logger.error("Not 2 readings generated for all data.")
            return {'status': False, 'message': "Error in generate_xrf_reading, not 2 readings generated for all", 'data': None}
    except Exception as e:
        logger.exception(f"Exception in generate_xrf_reading: {str(e)}")
        return {'status': False, 'message': "Error in generate_xrf_reading", 'data': e}

def generate_metal_values(purity):
    try:
        values = {}
        if purity == str(22):
            while True:
                values['au'] = round(random.uniform(916.77, 917.80), 3)
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
        elif purity == str(14):
            while True:
                values['au'] = round(random.uniform(585.3, 595.0), 3)
                values['ag'] = round(random.uniform(100.0, 400.0), 3)
                values['zn'] = round(random.uniform(20.0, 70.0), 3)
                values['cu'] = round(1000 - values['au'] - values['ag'] - values['zn'], 3)
                if (values['au'] + values['ag'] + values['cu'] + values['zn']) == 1000:
                    return values
        elif purity == str(24):
            while True:
                values['au'] = round(995.000, 3)
                values['ag'] = round(5.000, 3)
                values['zn'] = round(0, 3)
                values['cu'] = round(0, 3)
                if (values['au'] + values['ag'] + values['cu'] + values['zn']) == 1000:
                    return values
        else:
            logger.error(f"Purity {purity} not valid. Must be 14, 18, or 22.")
            return {'status': False, 'message': "Error in generate_metal_values, purity not 14, 18, 22 or 24", 'data': None}
    except Exception as e:
        logger.exception(f"Exception in generate_metal_values: {str(e)}")
        return {'status': False, 'message': "Error in generate_metal_values", 'data': e}


@app.route("/send_data", methods=["POST"])
def send_data():
    try:
        if request.method == "POST":
            res_job_data = get_cache("job_data.json")
            if res_job_data['status']:
                job_data = res_job_data['data']
                logger.debug(f"Job data loaded: {job_data}")
                
                res_final_xrf_data = get_cache("put_data.json")
                if res_final_xrf_data['status']:
                    final_xrf_data = res_final_xrf_data['data']


                    if job_data["machine"] == "machine1":
                        machine_data = JSON_DATA_MICROSPEC
                        machine_name = "MICROSPEC"
                    elif job_data["machine"] == "machine2":
                        machine_data = JSON_DATA_FISCHER
                        machine_name = "FISCHER"
                    else:
                        logger.error("Invalid machine specified.")
                        return {'status': False, 'message': "Invalid machine specified.", 'data': None}
                    

                    send_data_res = make_api_call(job_data['request_num'], job_data['job_num'], machine_data, final_xrf_data)
                    if send_data_res['status']:
                        # save the data in a csv file
                        csv_file = f"XRF_Data_R{job_data['request_num']}_J{job_data['job_num']}_{machine_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
                        csv_file_path = os.path.join(os.getcwd(), 'saved_files', csv_file)
                        # save the data in a csv file by pandas
                        df = pd.DataFrame(final_xrf_data)
                        df.to_csv(csv_file_path, index=False)
                        logger.info(f"Data saved in CSV file: {csv_file_path}")
                        # load the data as pandas dataframe
                        clear_cache_file("job_data.json")
                        clear_cache_file("put_data.json")
                        clear_cache_file("get_result.json")
                        clear_cache_file("get_data.json")
                        logger.info(f"Job {job_data['job_num']} completed successfully from {machine_name}")
                        return render_template("home.html", res_data={'data': 'Ready to use'}, put_data={'data': ['Ready']}, message_data={'data': 'Data Sent'})
                    else:
                        logger.error(f"Error in sending data: {send_data_res['message']}")
                        return send_data_res
                else:
                    logger.error(f"Error in loading final XRF data: {res_final_xrf_data['message']}")
                    return res_final_xrf_data
    except Exception as e:
        logger.exception(f"Exception in send_data: {str(e)}")
        return {'status': False, 'message': "Error in send_data - whole", 'data': e}

def make_api_call(request_number, job_number, machine_data, final_xrf_data):
    try:
        # postxrfJobdetails
        post_url = API_URL + f"reqno={request_number}&jobno={job_number}"
        logger.debug(f"Making API GET request to: {post_url}")
        res = requests.get(post_url, json=machine_data)
        
        # postxrfJobdetails
        POST_URL = f"https://huid.manakonline.in/MANAK/getxrfJobdetails?reqno={request_number}&jobno={job_number}"
        machine_data_to_send = machine_data.copy()
        machine_data_to_send['xrfdetail'] = final_xrf_data
        logger.debug(f"Making API POST request to: {POST_URL} with data: {machine_data_to_send}")

        res = requests.post(POST_URL, json=machine_data_to_send)
        if res.status_code == 200:
            logger.info("Data sent successfully.")
            return {'status': True, 'message': "Data sent successfully", 'data': res.json()}
        else:
            logger.error(f"Error in API response, status code not 200: {res.json()}")
            return {'status': False, 'message': "Error in send_data, status code not 200", 'data': None}
    except Exception as e:
        logger.exception(f"Exception in make_api_call: {str(e)}")
        return {'status': False, 'message': "Error in make_api_call", 'data': e}

def put_cache(filename, data):
    try:
        with open(filename, 'w') as f:
            json.dump(data, f)
        logger.info(f"Data successfully cached in {filename}.")
        return {'status': True, 'message': "Data put in cache successfully", 'data': None}
    except Exception as e:
        logger.exception(f"Exception in put_cache: {str(e)}")
        return {'status': False, 'message': "Error in put_cache", 'data': e}

def get_cache(filename):
    try:
        if os.path.getsize(filename) == 0:
            logger.error(f"File {filename} is empty.")
            return {'status': False, 'message': f"File {filename} is empty.", 'data': None}

        with open(filename, 'r') as f:
            data = json.load(f)
            if not data:
                logger.error(f"File {filename} contains no data.")
                return {'status': False, 'message': f"File {filename} contains no data.", 'data': None}
        logger.info(f"Data fetched from cache successfully from {filename}.")
        return {'status': True, 'message': "Data fetched from cache successfully", 'data': data}
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {filename}: {e}")
        return {'status': False, 'message': f"Error decoding JSON from {filename}: {e}", 'data': None}
    except Exception as e:
        logger.exception(f"Exception in get_cache: {str(e)}")
        return {'status': False, 'message': "Error in get_cache", 'data': e}

def clear_cache_file(filename):
    try:
        with open(filename, 'w') as file:
            json.dump({}, file)
        logger.info(f"Cache file {filename} cleared.")
    except Exception as e:
        logger.exception(f"Exception in clearing cache file {filename}: {str(e)}")

if __name__ == "__main__":
    # check and create the saved_files directory
    saved_files_dir = os.path.join(os.getcwd(), 'saved_files')
    os.makedirs(saved_files_dir, exist_ok=True)
    # check and create the logs directory
    log_dir = os.path.join(os.getcwd(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    # check and create the app.log file
    app_log_path = os.path.join(log_dir, 'app.log')
    # check and create the cache files
    cache_files = ["job_data.json", "put_data.json", "get_result.json", "get_data.json"]
    for file in cache_files:
        if not pathlib.Path(file).exists():
            with open(file, 'w') as f:
                json.dump({}, f)
    app.run(debug=True, port=5003, host='0.0.0.0')
