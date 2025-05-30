import logging # Import logging
from flask import Flask, render_template, request
from longview_app.fhir_parser import load_all_patients_data
from datetime import datetime

# Basic Logging Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Get a logger for this module

app = Flask(__name__)
logger.info("OneView application starting...")

# Load all patient data when the application starts
all_patients_data = load_all_patients_data()
if not all_patients_data:
    logger.warning("No patient data was loaded. Patient search and detail view will not work.")
else:
    logger.info(f"Successfully loaded {len(all_patients_data)} patient records.")

def get_patient_by_id(patient_id):
    """Helper function to find a patient by their ID."""
    for patient in all_patients_data:
        if patient.get('patient_id') == patient_id:
            return patient
    return None

def calculate_age(dob_str):
    """Calculate age from DOB string (YYYY-MM-DD)."""
    if not dob_str:
        return None
    try:
        dob = datetime.strptime(dob_str, "%Y-%m-%d")
        today = datetime.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except ValueError:
        return None # Invalid date format

@app.route('/', methods=['GET', 'POST'])
def index():
    search_results = []
    search_query_display = ""
    selected_patient_details = None
    patient_age = None

    # Check if a specific patient is being requested via GET parameter
    patient_id_from_query = request.args.get('patient_id')
    sort_by_param = request.args.get('sort_by', 'date') # Default sort by date
    sort_order_param = request.args.get('sort_order', 'desc') # Default sort descending

    if patient_id_from_query:
        logger.info(f"Viewing details for patient ID: {patient_id_from_query}")
        selected_patient_details = get_patient_by_id(patient_id_from_query)
        if selected_patient_details:
            patient_age = calculate_age(selected_patient_details.get('dob'))
            search_results = [] 
            search_query_display = ""

            # Sort recent encounters
            if sort_by_param == 'date' and selected_patient_details.get('recent_encounters'):
                def get_date_key(encounter):
                    # Handles potential missing dates or varying formats for robustness.
                    # Returns a datetime object for comparison or a min/max datetime to push unparseable dates to one end.
                    date_str = encounter.get('date')
                    if not date_str:
                        # If sort order is ascending, push None dates to the end, else to the beginning.
                        return datetime.max if sort_order_param == 'asc' else datetime.min
                    try:
                        # Attempt to parse different common FHIR date/datetime formats
                        if 'T' in date_str:
                            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        else:
                            return datetime.strptime(date_str, '%Y-%m-%d')
                    except ValueError:
                        # If parsing fails, treat as an "unknown" date
                        return datetime.max if sort_order_param == 'asc' else datetime.min
                
                selected_patient_details['recent_encounters'].sort(
                    key=get_date_key,
                    reverse=(sort_order_param == 'desc')
                )

    elif request.method == 'POST':
        search_query = request.form.get('search_query', '').strip()
        search_query_display = search_query
        logger.info(f"Search performed with query: '{search_query}'")

        if search_query:
            for patient in all_patients_data:
                if patient.get('patient_id') == search_query:
                    search_results.append(patient)
                    continue
                patient_name = patient.get('full_name', '')
                if search_query.lower() in patient_name.lower():
                    search_results.append(patient)
                    continue
        # If POST but empty query, search_results remains empty

    return render_template('index.html', 
                           patients=search_results, 
                           search_query=search_query_display,
                           num_results=len(search_results),
                           selected_patient=selected_patient_details,
                           patient_age=patient_age,
                           current_sort_by=sort_by_param,
                           current_sort_order=sort_order_param)

if __name__ == '__main__':
    # Note: Flask's development server's default logging might override basicConfig in some cases.
    # For production, a more robust logging setup (e.g., with Gunicorn) is recommended.
    # The logger.info calls will still work.
    app.run(debug=True)
