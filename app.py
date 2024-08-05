from flask import Flask, render_template, request, redirect
import requests
import json
import random
import csv
import os
import pathlib
from datetime import datetime
import logging
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
    logger.info("Rendering home page.")
    return render_template("home.html", res_data={'data': ['Ready to use']}, put_data={'data': ['Ready']})

@app.route("/get_data", methods=["POST"])
def get_data():
    if request.method == "POST":
        data = request.form.to_dict()
        logger.debug(f"Received form data: {data}")

        if not is_dict_empty(data):
            machine_data = None
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
                        return render_template("home.html", res_data=res_data, put_data={'data': ['Lesgo']})
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
        print(get_url)
        logger.debug(f"Making API request to: {get_url} with data: {machine_data}")
        res = requests.get(get_url, json=machine_data)
        logger.debug(f"Raw response content: {res.text}")  # Log raw response content

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


def is_dict_empty(d):
    try:
        for value in d.values():
            if value != "":
                return False
        logger.info("Dictionary is empty.")
        return True
    except Exception as e:
        logger.exception(f"Exception in is_dict_empty: {str(e)}")
        return {'status': False, 'message': "Error in is_dict_empty", 'data': e}

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

                send_data = generate_xrf_reading(get_result['data'])
                if send_data['status']:
                    put_result = put_cache("put_data.json", send_data['data'])
                    if put_result['status']:
                        send_data['generated_readings'] = len(send_data['data'])
                        logger.info("Data generated and saved successfully.")
                        return render_template("home.html", res_data=send_data, put_data=send_data)
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
                send_temp['declare_purity'] = send_temp['declare_purity'][3:6]
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
        else:
            logger.error(f"Purity {purity} not valid. Must be 14, 18, or 22.")
            return {'status': False, 'message': "Error in generate_metal_values, purity not 14, 18 or 22", 'data': None}
    except Exception as e:
        logger.exception(f"Exception in generate_metal_values: {str(e)}")
        return {'status': False, 'message': "Error in generate_metal_values", 'data': e}

def generate_filenames(jobid):
    directory = os.path.join(os.getcwd(), 'xrfcsv')
    if not os.path.exists(directory):
        os.makedirs(directory)
    return os.path.join(directory, f'{jobid}.csv')

def reorder_dict(dictionary, fieldnames):
    return {key: dictionary[key] for key in fieldnames}

def log_dicts_to_csv(data, jobid, reqno, machine):
    try:
        filename = generate_filenames(jobid)
        logger.debug(f"Saving data to {filename}")
        fieldnames = ['tag_id', 'declare_purity', 'reading', 'gold', 'copper', 'silver', 'cadmium', 'iridium',
                      'nickel', 'osmium', 'platinum', 'palladium', 'rhodium', 'ruthenium']
        file_exists = os.path.isfile(filename)

        with open(filename, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                logger.debug("Writing CSV header.")
                writer.writeheader()  # Write the header row if the file is newly created

            for d in data:
                reordered_dict = reorder_dict(d, fieldnames)
                writer.writerow(reordered_dict)  # Write each reordered dictionary as a row in the CSV file

        with open(filename, "a", newline='') as file:
            csvwrite = csv.writer(file)
            jobid_info = f"Job Id: {jobid}"
            reqno_info = f"Req No: {reqno}"
            count = f"Number of pieces: {len(data) / 2}"
            today = datetime.today()
            date = f"{today.day}/{today.month}/{today.year}"
            donedate = f"Completion Date: {date}"
            machine_info = f"Machine: {machine}"
            metadata = [jobid_info, reqno_info, count, donedate, machine_info]
            csvwrite.writerow(metadata)  # Write additional metadata as a new row
        logger.info(f"Data logged successfully for jobid: {jobid}")
        return {'status': True, 'message': "Data logged successfully", 'data': None}
    except Exception as e:
        logger.exception(f"Exception in log_dicts_to_csv: {str(e)}")
        return {'status': False, 'message': "Error in log_dicts_to_csv", 'data': e}

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
                    logger.debug(f"Final XRF data loaded: {final_xrf_data}")

                    if job_data["machine"] == "machine1":
                        machine_data = JSON_DATA_MICROSPEC
                        machine_name = "MICROSPEC"
                    elif job_data["machine"] == "machine2":
                        machine_data = JSON_DATA_FISCHER
                        machine_name = "FISCHER"
                    else:
                        logger.error("Invalid machine specified.")
                        return {'status': False, 'message': "Invalid machine specified.", 'data': None}

                    send_data = make_api_call(job_data['request_num'], job_data['job_num'], machine_data, final_xrf_data)
                    if send_data['status']:
                        res_log_dicts = log_dicts_to_csv(final_xrf_data, job_data['job_num'], job_data['request_num'], machine_name)
                        if res_log_dicts['status']:
                            clear_cache_file("job_data.json")
                            clear_cache_file("put_data.json")
                            clear_cache_file("get_result.json")
                            logger.info(f"Job {job_data['job_num']} completed successfully from {machine_name}")
                            return render_template("home.html", res_data={'data': ['Complete']}, put_data={'data': ['completed']})
                        else:
                            logger.error(f"Error in logging dictionaries: {res_log_dicts['message']}")
                            return res_log_dicts
                    else:
                        logger.error(f"Error in making API call: {send_data['message']}")
                        return send_data
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
        machine_data['xrfdetail'] = final_xrf_data
        logger.debug(f"Making API POST request to: {POST_URL} with data: {machine_data}")

        res = requests.post(POST_URL, json=machine_data)
        if res.status_code == 200:
            logger.info("Data sent successfully.")
            return {'status': True, 'message': "Data sent successfully", 'data': res.json()}
        else:
            logger.error(f"Error in API response, status code not 200: {res.json()}")
            return {'status': False, 'message': "Error in send_data, status code not 200", 'data': res.json()}
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
    app.run(debug=True, port=5003, host='0.0.0.0')
