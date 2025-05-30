from flask import Flask, render_template, request
from longview_app.fhir_parser import load_all_patients_data
from datetime import datetime

app = Flask(__name__)

# Load all patient data when the application starts
all_patients_data = load_all_patients_data()
if not all_patients_data:
    print("Warning: No patient data was loaded. Patient search and detail view will not work.")

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

    if patient_id_from_query:
        selected_patient_details = get_patient_by_id(patient_id_from_query)
        if selected_patient_details:
            patient_age = calculate_age(selected_patient_details.get('dob'))
            # No search results to display when showing patient details
            search_results = [] 
            search_query_display = ""

    elif request.method == 'POST':
        search_query = request.form.get('search_query', '').strip()
        search_query_display = search_query

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
                           patient_age=patient_age)

if __name__ == '__main__':
    print(f"Loaded {len(all_patients_data)} patient records.")
    app.run(debug=True)
