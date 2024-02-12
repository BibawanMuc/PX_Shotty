import streamlit as st
import pandas as pd
import sqlite3
import os
import datetime
from tkinter import filedialog

# Ensure the folder exists
os.makedirs('uploaded_images', exist_ok=True)

# Current date in the format DDMMYY
current_date = datetime.datetime.now().strftime("%d%m%y")

# Convert seconds to timecode
def seconds_to_timecode(total_seconds, fps):
    hours = total_seconds // 3600
    total_seconds %= 3600
    minutes = total_seconds // 60
    total_seconds %= 60
    frames = int(total_seconds * fps) % fps
    return f"{int(hours):02}:{int(minutes):02}:{int(total_seconds):02}:{frames:02}"

# Export the data to an EDL file
def export_edl(project_name, file_path):
    with sqlite3.connect('data.db') as conn:
        df = pd.read_sql(f"SELECT * FROM shotlist WHERE project='{project_name}'", conn)

    # Sort the DataFrame by "scene", "shot", and "take"
    df = df.sort_values(by=['scene', 'shot', 'take'])

    with open(file_path, "w") as f:
        f.write(f"TITLE: {project_name}\n")
        f.write("FCM: NON-DROP FRAME\n\n")
        
        accumulated_duration = 0
        event_number = 1  # Start event numbering from 1
        for i, row in df.iterrows():
            start_time = accumulated_duration
            end_time = start_time + row["duration"]
            
            start_tc = seconds_to_timecode(start_time, row['fps'])
            end_tc = seconds_to_timecode(end_time, row['fps'])
            
            # Write the video track entry with a unique event number
            f.write(f"{event_number:03}  AX       V     C        {start_tc} {end_tc} {start_tc} {end_tc}\n")
            
            # Only use the "Kamera Clip" as the clip name with ".mov" extension
            reel_name = row["clip_name"].split('.')[0]
            clip_name = f"{reel_name}.mov"
            
            f.write(f"* FROM CLIP NAME: {clip_name}\n")
            
            # Increment the event number for the next entry
            event_number += 1
            
            # Write the audio entry with the code `AA` and specify the active audio tracks from A1 to A8
            f.write(f"{event_number:03}  AX       AA    C        {start_tc} {end_tc} {start_tc} {end_tc}\n")
            f.write(f"* FROM CLIP NAME: {clip_name}\n")
            for audio_track in range(1, 9):  # A1 to A8
                f.write(f"* AUDIO LEVEL AT 00:00:00:00 IS -0.00 DB  (REEL AX A{audio_track})\n")
            f.write("AUD  1 2 3 4 5 6 7 8\n\n")  # Activate all audio tracks from A1 to A8
            
            # Increment the event number for the next entry
            event_number += 1
            
            # Increment the accumulated duration for the next clip
            accumulated_duration += row["duration"]

# Export the data to an Excel file
def export_excel(project_name, file_path):
    with sqlite3.connect('data.db') as conn:
        df = pd.read_sql(f"SELECT * FROM shotlist WHERE project='{project_name}'", conn)

    # Sort the DataFrame by "scene", "shot", and "take"
    df = df.sort_values(by=['scene', 'shot', 'take'])

    df.to_excel(file_path, index=False)

# Initialize the SQLite3 database
def init_db():
    with sqlite3.connect('data.db') as conn:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS shotlist (
            created_by TEXT,
            id INTEGER PRIMARY KEY,
            project TEXT,
            scene INTEGER,
            shot INTEGER,
            take INTEGER,
            description TEXT,
            location TEXT,
            time_of_day TEXT,
            camera_settings TEXT,
            actors TEXT,
            props TEXT,
            notes TEXT,
            duration INTEGER,
            audio TEXT,
            fps INTEGER,
            camera_options TEXT,
            clip_name TEXT,
            image_path TEXT
        )
        ''')

# Save data to the SQLite3 database
def save_to_db(project, record):
    with sqlite3.connect('data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO shotlist (created_by, project, scene, shot, take, description, location, time_of_day, camera_settings, actors, props, notes, duration, audio, fps, camera_options, clip_name, image_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ("unbekannt", project, record['scene'], record['shot'], record['take'], record['description'], record['location'], record['time_of_day'], record['camera_settings'], record['actors'], record['props'], record['notes'], record['duration'], record['audio'], record['fps'], record['camera_options'], record['clip_name'], record['image_path']))
        conn.commit()

# Update data in the SQLite3 database
def update_db(project, scene, shot, take, updated_record):
    with sqlite3.connect('data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE shotlist 
        SET description=?, location=?, time_of_day=?, camera_settings=?, actors=?, props=?, notes=?, duration=?, audio=?, fps=?, camera_options=?, clip_name=?, image_path=?
        WHERE project=? AND scene=? AND shot=? AND take=?
        ''', (updated_record['description'], updated_record['location'], updated_record['time_of_day'], updated_record['camera_settings'], updated_record['actors'], updated_record['props'], updated_record['notes'], updated_record['duration'], updated_record['audio'], updated_record['fps'], updated_record['camera_options'], updated_record['clip_name'], updated_record['image_path'], project, scene, shot, take))
        conn.commit()

# Fetch data from the SQLite3 database
def fetch_all_data(project):
    with sqlite3.connect('data.db') as conn:
        df = pd.read_sql(f"SELECT * FROM shotlist WHERE project='{project}'", conn)
    return df

# Get a specific record from the SQLite3 database
def get_record(project, scene, shot, take):
    with sqlite3.connect('data.db') as conn:
        df = pd.read_sql(f"SELECT * FROM shotlist WHERE project='{project}' AND scene={scene} AND shot={shot} AND take={take}", conn)
    if not df.empty:
        return df.iloc[0]
    else:
        return None

# Get all unique projects from the SQLite3 database
def get_all_projects():
    with sqlite3.connect('data.db') as conn:
        df = pd.read_sql("SELECT DISTINCT project FROM shotlist", conn)
    return df['project'].tolist()

init_db()

# Initialize session state
if 'current_project' not in st.session_state:
    st.session_state.current_project = None
if 'editing' not in st.session_state:
    st.session_state.editing = False
if 'selected_scene' not in st.session_state:
    st.session_state.selected_scene = None
if 'selected_shot' not in st.session_state:
    st.session_state.selected_shot = None
if 'selected_take' not in st.session_state:
    st.session_state.selected_take = None

# Sidebar for projects (EDL sessions)
project_name = st.sidebar.text_input("Job/Projekt/Dreh Name:")

all_projects = get_all_projects()

if st.sidebar.button("Neues Projekt"):
    if project_name and project_name not in all_projects:
        st.session_state.current_project = project_name
    else:
        st.sidebar.write("Projektname bereits vorhanden oder leer!")

# Option to switch between projects
if all_projects:
    selected_project = st.sidebar.selectbox("Wählen Sie ein Projekt:", all_projects)
    if st.sidebar.button("Projekt laden"):
        st.session_state.current_project = selected_project

# Option to edit records
if st.session_state.current_project and not st.session_state.editing:
    if st.sidebar.button("Daten bearbeiten"):
        st.session_state.editing = True

# Option to stop editing records
if st.session_state.editing:
    if st.sidebar.button("Bearbeitung stoppen"):
        st.session_state.editing = False
        st.session_state.selected_scene = None
        st.session_state.selected_shot = None
        st.session_state.selected_take = None

st.title(f"Shotliste für {st.session_state.current_project}" if st.session_state.current_project else "Bitte wählen Sie ein Projekt")

# Fetch the data from the database
df = fetch_all_data(st.session_state.current_project)

if st.session_state.current_project:
    # If in editing mode, show edit form
    if st.session_state.editing:
        scenes = df['scene'].unique().tolist()
        selected_scene = st.selectbox("Szene auswählen", scenes)
        selected_shot_df = df[df['scene'] == selected_scene]
        shots = selected_shot_df['shot'].unique().tolist()
        selected_shot = st.selectbox("Shot auswählen", shots)
        selected_take_df = selected_shot_df[selected_shot_df['shot'] == selected_shot]
        takes = selected_take_df['take'].unique().tolist()
        selected_take = st.selectbox("Take auswählen", takes)

        # Set session state for selected scene, shot, take
        st.session_state.selected_scene = selected_scene
        st.session_state.selected_shot = selected_shot
        st.session_state.selected_take = selected_take

        record_to_edit = get_record(st.session_state.current_project, st.session_state.selected_scene, st.session_state.selected_shot, st.session_state.selected_take)

        if record_to_edit is not None:
            with st.form(key='edit_form'):
                # Create three columns for input fields
                col1, col2, col3 = st.columns(3)
                
                # Input fields for the first column
                with col1:
                    description = st.text_input("Beschreibung", record_to_edit['description'])
                    location = st.text_input("Ort", record_to_edit['location'])
                    time_of_day = st.selectbox("Tageszeit", ["Morgen", "Mittag", "Nachmittag", "Abend", "Nacht"], index=["Morgen", "Mittag", "Nachmittag", "Abend", "Nacht"].index(record_to_edit['time_of_day']))
                    uploaded_image = st.file_uploader("Bild hochladen", type=["jpg", "jpeg", "png"])
                    if uploaded_image:
                        image_path = os.path.join("uploaded_images", f"{st.session_state.selected_scene}_{st.session_state.selected_shot}_{st.session_state.selected_take}.jpg")
                        with open(image_path, "wb") as f:
                            f.write(uploaded_image.getvalue())
                    else:
                        image_path = record_to_edit['image_path']

                # Input fields for the second column
                with col2:
                    camera_settings = st.selectbox("Kameraeinstellungen", ["Totale", "Halb Total", "Halb Nah", "Nah", "CloseUp", "Detail"], index=["Totale", "Halb Total", "Halb Nah", "Nah", "CloseUp", "Detail"].index(record_to_edit['camera_settings']))
                    actors = st.text_input("Schauspieler", record_to_edit['actors'])
                    props = st.text_input("Requisiten", record_to_edit['props'])
                    notes = st.text_area("Notizen", record_to_edit['notes'])

                # Input fields for the third column
                with col3:
                    reel_name = st.text_input("Kamera Clip", record_to_edit['clip_name'].split('.')[0])
                    duration = st.number_input("Dauer (in Sekunden)", min_value=1, value=record_to_edit['duration'])
                    audio = st.selectbox("Audio", ["On", "Off"], index=["On", "Off"].index(record_to_edit['audio']))
                    fps_options = [25, 30, 50, 60, 100, 120]
                    fps = st.selectbox("FPS (Frames per Seconds)", fps_options, index=fps_options.index(record_to_edit['fps']))
                    camera_options = ["UrsaMini 4K", "BMPCC 6k", "Red One"]
                    selected_camera = st.selectbox("Kamera", camera_options, index=camera_options.index(record_to_edit['camera_options']))
                    
                # Generate the clip name
                clip_name = f"{reel_name}.mov"

                updated_record = {
                    "description": description,
                    "location": location,
                    "time_of_day": time_of_day,
                    "camera_settings": camera_settings,
                    "actors": actors,
                    "props": props,
                    "notes": notes,
                    "duration": duration,
                    "audio": audio,
                    "fps": fps,
                    "camera_options": selected_camera,
                    "clip_name": clip_name,
                    "image_path": image_path
                }

                if st.form_submit_button("Änderungen speichern"):
                    update_db(st.session_state.current_project, st.session_state.selected_scene, st.session_state.selected_shot, st.session_state.selected_take, updated_record)

    else:  # If not in editing mode, show regular form
        with st.form(key='shotlist_form'):
            # Create three columns for input fields
            col1, col2, col3 = st.columns(3)
            
            # Input fields for the first column
            with col1:
                scene = st.number_input("Szene", min_value=1)
                shot = st.number_input("Shot", min_value=1)
                take = st.number_input("Take", min_value=1)
                description = st.text_input("Beschreibung")
                location = st.text_input("Ort")
                time_of_day = st.selectbox("Tageszeit", ["Morgen", "Mittag", "Nachmittag", "Abend", "Nacht"])
                # uploaded_image = st.file_uploader("Bild hochladen", type=["jpg", "jpeg", "png"])
                
                # Process uploaded image
                image_path = None
                # if uploaded_image:
                #     image_path = os.path.join("uploaded_images", f"{scene}_{shot}_{take}.jpg")
                #     with open(image_path, "wb") as f:
                #         f.write(uploaded_image.getvalue())

            # Input fields for the second column
            with col2:
                camera_settings = st.selectbox("Kameraeinstellungen", ["Totale", "Halb Total", "Halb Nah", "Nah", "CloseUp", "Detail"])
                actors = st.text_input("Schauspieler")
                props = st.text_input("Requisiten")
                notes = st.text_area("Notizen")

            # Input fields for the third column
            with col3:
                reel_name = st.text_input("Kamera Clip")
                duration = st.number_input("Dauer (in Sekunden)", min_value=3)
                audio = st.selectbox("Audio", ["On", "Off"])
                fps_options = [25, 30, 50, 60, 100, 120]
                fps = st.selectbox("FPS (Frames per Seconds)", fps_options)
                camera_options = ["UrsaMini 4K", "BMPCC 6k", "Red One"]
                selected_camera = st.selectbox("Kamera", camera_options)
                    
                # Generate the clip name
                clip_name = f"{reel_name}.mov"

                # Save the record
                record = {
                    "scene": scene,
                    "shot": shot,
                    "take": take,
                    "description": description,
                    "location": location,
                    "time_of_day": time_of_day,
                    "camera_settings": camera_settings,
                    "actors": actors,
                    "props": props,
                    "notes": notes,
                    "duration": duration,
                    "audio": audio,
                    "fps": fps,
                    "camera_options": selected_camera,
                    "clip_name": clip_name,
                    "image_path": image_path
                }

                if st.form_submit_button("Hinzufügen"):
                    save_to_db(st.session_state.current_project, record)

        # Export the shotlist as EDL
        if st.button("EDL exportieren"):
            file_path = filedialog.asksaveasfilename(defaultextension=".edl", filetypes=[("Edit Decision List", "*.edl")])
            if file_path:
                export_edl(st.session_state.current_project, file_path)
                st.write(f"EDL für {st.session_state.current_project} exportiert")

        # Export the shotlist as Excel
        if st.button("Excel exportieren"):
            file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Workbook", "*.xlsx")])
            if file_path:
                export_excel(st.session_state.current_project, file_path)
                st.write(f"Excel-Datei für {st.session_state.current_project} exportiert: [{file_path}]")
    
    # Check if the DataFrame is not empty before sorting
    if not df.empty:
        df = df.sort_values(["scene", "shot", "take"])
        st.table(df)
    else:
        st.write("Keine Daten vorhanden")
