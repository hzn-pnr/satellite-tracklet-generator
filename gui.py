# -*- coding: utf-8 -*-
# Created by: PyQt5 UI code generator 5.15.11
"""
Author: Pinar Hazan
Affiliation: Hacettepe University
Year: 2026

Description:
This source code has been developed as part of the thesis titled 
"Optical Tracklet Simulation for Space Surveillance and Tracking". 

Contact: pinarhazan99@gmail.com
"""

import sys
import os
import tempfile
import configparser
import traceback
from datetime import datetime

# PyQt5 Modules
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QObject
# Classes used directly without "QtWidgets." prefix in your code:
from PyQt5.QtWidgets import QMessageBox, QColorDialog, QLineEdit

# Project Modules
from controller import TrackletSimulationController
from tle_fetcher import SpaceTrackClient


class SimulationWorker(QObject):
    finished = pyqtSignal(dict)      # Returns data upon completion
    error = pyqtSignal(str)          # If an error occurs
    log_signal = pyqtSignal(str)     # Carries log messages to the GUI
    progress = pyqtSignal(int)

    def __init__(self, temp_txt_path):
        super().__init__()
        self.temp_txt_path = temp_txt_path
        self._is_interrupted = False

    def stop(self):
        """Activates the stop flag when called externally."""
        self._is_interrupted = True

    def _check_interruption(self):
        """The controller calls this method to check if it should stop."""
        if self._is_interrupted:
            raise InterruptedError("Simulation stopped by user.")

    def run(self):
        try:
            controller = TrackletSimulationController(self.temp_txt_path)
            
            # Tell the Controller to send logs here.
            if hasattr(controller, 'set_log_callback'):
                controller.set_log_callback(self.log_signal.emit)

            if hasattr(controller, 'set_progress_callback'):
                controller.set_progress_callback(self.progress.emit)

            # Pass stop control to the controller.
            if hasattr(controller, 'set_stop_check_callback'):
                controller.set_stop_check_callback(self._check_interruption)
            
            outputs = controller.run()
            self.finished.emit(outputs)

        except InterruptedError:
            # Lands here when the stop button is pressed
            # Send as an info message rather than an error
            self.error.emit("Simulation stopped by user.")

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)


class CatalogFetcherThread(QThread):
    result_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    # Accept the client object
    def __init__(self, client: SpaceTrackClient): 
        super().__init__()
        self.client = client 

    def run(self):
        try:
            # Call the method on the client object ---
            names = self.client.fetch_satellite_catalog() 
            self.result_ready.emit(names)
        except Exception as e:
            self.error_occurred.emit(str(e))

class TLEFetchExtension:
    #  Accept the client object ---
    def __init__(self, parent, client: SpaceTrackClient): 
        self.parent = parent
        self.client = client 

    def fetch_tle_clicked(self):
        name_or_id = self.parent.sat_name_combo.currentText().strip()
        year = self.parent.year_in.text()
        month = self.parent.month_in.text()
        day = self.parent.day_in.text()
        hour = self.parent.hour.text()
        minute = self.parent.minute.text()
        second = self.parent.second.text()

        try:
            dt = datetime(
                int(year), int(month), int(day),
                int(hour), int(minute), int(float(second))
            ).isoformat()

            # Call the method on the client object and handle None return 
            tle_pair = self.client.get_closest_tle(name_or_id, dt) 
            
            if tle_pair: # Check if a TLE was actually found
                tle1, tle2 = tle_pair 
                self.parent.tle1_in.setText(tle1)
                self.parent.tle2_in.setText(tle2)
                QMessageBox.information(
                    self.parent.centralwidget,
                    "TLE Fetch",
                    "TLE data fetched successfully."
                )
            else: # Handle the case where no TLE was found
                QMessageBox.warning(
                    self.parent.centralwidget,
                    "TLE Not Found",
                    f"No TLE found for '{name_or_id}' in the specified date range."
                )
        except Exception as e:
            QMessageBox.critical(
                self.parent.centralwidget,
                "TLE Fetch Failed",
                str(e)
            )

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.setWindowTitle("Satellite Tracklet Simulator")
        MainWindow.resize(1311, 792)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        MainWindow.setStyleSheet("""
        QWidget {
            background-color: #1e1e1e;
            color: #ffffff;
        }
        QPushButton {
            background-color: #444444;
            color: white;
            padding: 6px;
            border: 1px solid #666666;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #666666;
        }
        QLineEdit, QComboBox, QTextEdit {
            background-color: #2c2c2c;
            color: white;
            border: 1px solid #555555;
            padding: 4px;
            min-height: 28px;
        }
        QGroupBox {
            border: 1px solid #888888;
            margin-top: 10px;
            font-weight: bold;
            color: #cccccc;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 4px;
        }
        QLabel {
            color: #cccccc;
        }
        QMenuBar, QMenu {
            background-color: #2b2b2b;
            color: #c8c8c8;
        }
        """)

        main_layout = QtWidgets.QHBoxLayout(self.centralwidget)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QtWidgets.QWidget()
        scroll_area.setWidget(scroll_content)
        scroll_layout = QtWidgets.QHBoxLayout(scroll_content)

        left_col = QtWidgets.QVBoxLayout()
        left_col.setSpacing(20)
        right_col = QtWidgets.QVBoxLayout()
        right_col.setSpacing(20)

        def add_labeled_input(label, placeholder="", width=200):
            row = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            label_widget = QtWidgets.QLabel(label)
            input_widget = QtWidgets.QLineEdit()
            input_widget.setPlaceholderText(placeholder)
            input_widget.setFixedWidth(width)
            input_widget.setFixedHeight(28)
            layout.addWidget(label_widget)
            layout.addWidget(input_widget)
            row.input = input_widget
            return row, input_widget

        def create_group(title, rows, spacing=12):
            box = QtWidgets.QGroupBox(title)
            layout = QtWidgets.QVBoxLayout()
            layout.setSpacing(spacing)  
            for row in rows:
                layout.addWidget(row)
            box.setLayout(layout)
            return box

        # Observation Site
        lat, self.latitude_in = add_labeled_input("Latitude (°):", "32.5")
        lon, self.longitude_in = add_labeled_input("Longitude (°):", "39.6")
        elev, self.elevation_in = add_labeled_input("Elevation (m):", "146")
        obs_group = create_group("Observation Site", [lat, lon, elev])
        left_col.addWidget(obs_group)

        # CCD
        x, self.ccd_in_x = add_labeled_input("Image Width (pix):", "1024")
        y, self.ccd_in_y = add_labeled_input("Image Height (pix):", "1024")
        psize, self.pixel_sixe_in = add_labeled_input("Pixel Size (mm):", "0.0048")
        pscale, self.pixel_scale_in = add_labeled_input("Pixel Scale (arcsec/pix):", "12.1")
        matrix = QtWidgets.QGridLayout()
        self.ccd1_1 = QtWidgets.QLineEdit(); self.ccd1_2 = QtWidgets.QLineEdit()
        self.ccd2_1 = QtWidgets.QLineEdit(); self.ccd2_2 = QtWidgets.QLineEdit()
        matrix.addWidget(self.ccd1_1, 0, 0); matrix.addWidget(self.ccd1_2, 0, 1)
        matrix.addWidget(self.ccd2_1, 1, 0); matrix.addWidget(self.ccd2_2, 1, 1)
        matrix_widget = QtWidgets.QGroupBox("CCD Matrix")
        matrix_widget.setLayout(matrix)
        ccd_group = create_group("CCD Settings", [x, y, psize, pscale, matrix_widget])
        left_col.addWidget(ccd_group)

        # Satellite Orbit Data
        name_lbl = QtWidgets.QLabel("Satellite Name:")
        self.sat_name_combo = QtWidgets.QComboBox()
        self.sat_name_combo.setEditable(True)
        self.get_tle_btn = QtWidgets.QPushButton("Get TLE")
        name_line = QtWidgets.QHBoxLayout()
        name_line.addWidget(name_lbl)
        name_line.addWidget(self.sat_name_combo)
        name_line.addWidget(self.get_tle_btn)
        tle1, self.tle1_in = add_labeled_input("TLE Line 1:", "", width=475)
        tle2, self.tle2_in = add_labeled_input("TLE Line 2:", "", width=475)
        sat_box = QtWidgets.QGroupBox("Satellite Orbit Data")
        sat_layout = QtWidgets.QVBoxLayout()
        sat_layout.addLayout(name_line)
        sat_layout.addWidget(tle1)
        sat_layout.addWidget(tle2)
        mag_row, self.target_mag_in = add_labeled_input("Target Magnitude:", "10.0")
        sat_layout.addWidget(mag_row)
        sat_box.setLayout(sat_layout)
        left_col.addWidget(sat_box)


        # --- Reference Image ---
        ref_row = QtWidgets.QWidget()
        ref_layout = QtWidgets.QHBoxLayout(ref_row)
        ref_layout.setContentsMargins(0, 0, 0, 0)
        ref_layout.addWidget(QtWidgets.QLabel("Reference Image:"))
        self.ref_image_in = QtWidgets.QLineEdit()
        self.ref_image_in.setPlaceholderText("Select reference .fits file (optional)")
        ref_layout.addWidget(self.ref_image_in, 1)
        self.ref_browse_btn = QtWidgets.QPushButton("📂")
        ref_layout.addWidget(self.ref_browse_btn)
        sat_layout.addWidget(ref_row)

        # --- SP3 inputs ---
        sp3_row = QtWidgets.QWidget()
        sp3_layout = QtWidgets.QHBoxLayout(sp3_row)
        sp3_layout.setContentsMargins(0, 0, 0, 0)
        sp3_layout.addWidget(QtWidgets.QLabel("SP3 File:"))
        self.sp3_path_in = QtWidgets.QLineEdit()
        self.sp3_path_in.setPlaceholderText("Select .sp3 ephemeris file")
        sp3_layout.addWidget(self.sp3_path_in, 1)
        self.sp3_browse_btn = QtWidgets.QPushButton("📂")
        sp3_layout.addWidget(self.sp3_browse_btn)

        sp3id_row, self.sp3_sat_id_in = add_labeled_input("SP3 Satellite ID:", "e.g. L39 / G04", width=200)

    
        sat_layout.addWidget(sp3_row)
        sat_layout.addWidget(sp3id_row)

        # Output path
        path_row = QtWidgets.QWidget()
        path_layout = QtWidgets.QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
       
        path_layout.addWidget(QtWidgets.QLabel("Output Directory:"))
        self.output_in = QtWidgets.QLineEdit()
        self.output_in.setPlaceholderText("Select output directory") 
        path_layout.addWidget(self.output_in)
        self.browse_btn = QtWidgets.QPushButton("📂")
        path_layout.addWidget(self.browse_btn)
        left_col.addWidget(path_row)

        name_row = QtWidgets.QWidget()
        name_layout = QtWidgets.QHBoxLayout(name_row)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.addWidget(QtWidgets.QLabel("Output File Name:"))
        self.output_name_in = QtWidgets.QLineEdit()
        self.output_name_in.setPlaceholderText("e.g. final_image.png")
        name_layout.addWidget(self.output_name_in)
        left_col.addWidget(name_row)

        self.selected_frame_color = '#FF0000' 

        frame_group = QtWidgets.QGroupBox("Stellarium Frame Options")
        frame_layout = QtWidgets.QVBoxLayout()
        
        self.frame_checkbox = QtWidgets.QCheckBox("Add colored frame to simulated image")
        frame_layout.addWidget(self.frame_checkbox)

        color_layout = QtWidgets.QHBoxLayout()
        
        self.frame_color_btn = QtWidgets.QPushButton("Select Frame Color")
        color_layout.addWidget(self.frame_color_btn, 1) 

        self.frame_color_display = QtWidgets.QLabel()
        self.frame_color_display.setMinimumWidth(40)

        self.frame_color_display.setStyleSheet(f"background-color: {self.selected_frame_color}; border: 1px solid #888888;")
        color_layout.addWidget(self.frame_color_display)

        frame_layout.addLayout(color_layout)
        frame_group.setLayout(frame_layout)
        
        left_col.addWidget(frame_group)

        self.frame_color_btn.setEnabled(False)
        self.frame_color_display.setEnabled(False)
        self.frame_checkbox.toggled.connect(self.frame_color_btn.setEnabled)
        self.frame_checkbox.toggled.connect(self.frame_color_display.setEnabled)
        
        self.frame_color_btn.clicked.connect(self.select_frame_color)

        # Telescope View
        ra, self.ra_in = add_labeled_input("RA (°):", "125.62")
        dec, self.dec_in = add_labeled_input("DEC (°):", "45.85")
        rot, self.rotation_in = add_labeled_input("Rotation (°):", "1.5")
        fov, self.fov_in = add_labeled_input("FoV (°):", "0.46")
        exposure, self.exposure_in = add_labeled_input("Exposure (sec):", "5")

        mode_row = QtWidgets.QWidget()
        mode_layout = QtWidgets.QHBoxLayout(mode_row)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.addWidget(QtWidgets.QLabel("Tracking Mode:"))
        
        self.tracking_mode_in = QtWidgets.QComboBox()
        self.tracking_mode_in.addItems(["parking", "sidereal", "target"]) 
        self.tracking_mode_in.setFixedWidth(120)
        
        mode_layout.addWidget(self.tracking_mode_in)
        mode_layout.addStretch()

        star_mag_widget = QtWidgets.QWidget()
        star_mag_layout = QtWidgets.QHBoxLayout(star_mag_widget)
        star_mag_layout.setContentsMargins(0, 0, 0, 0)
        
        star_mag_layout.addWidget(QtWidgets.QLabel("Star Mag Range:"))
        
        self.star_min_mag_in = QtWidgets.QLineEdit()
        self.star_min_mag_in.setPlaceholderText("Min (10)")
        self.star_min_mag_in.setFixedWidth(60)
        
        self.star_max_mag_in = QtWidgets.QLineEdit()
        self.star_max_mag_in.setPlaceholderText("Max (18)")
        self.star_max_mag_in.setFixedWidth(60)
        
        star_mag_layout.addWidget(self.star_min_mag_in)
        star_mag_layout.addWidget(QtWidgets.QLabel("-"))
        star_mag_layout.addWidget(self.star_max_mag_in)
        star_mag_layout.addStretch() 

        right_col.addWidget(create_group("Telescope View", [ra, dec, rot, fov, exposure, mode_row, star_mag_widget]))

        # Optical
        k, self.k_in = add_labeled_input("K Coefficient:", "0.5")
        zp, self.zero_point_in = add_labeled_input("Zero Point:", "25.1")
        bias, self.bias_in = add_labeled_input("Bias:", "0.5")
        flat, self.flat_in = add_labeled_input("Flat:", "1")
        gain, self.gain_in = add_labeled_input("Gain:", "1.5")
        bg_mag, self.bg_mag_in = add_labeled_input("Background Mag:", "16.0")
        rn, self.read_noise_in = add_labeled_input("Read Noise (e-):", "5.0")       
        dc, self.dark_current_in = add_labeled_input("Dark Current (e-/s):", "0.1")
        seeing, self.seeing_in = add_labeled_input("Seeing:", "1.2")
        right_col.addWidget(create_group("Atmospheric and Optical Effects", [k, zp, bias, flat, gain, bg_mag, rn, dc, seeing]))

        # Observation Time
        date_group = QtWidgets.QGroupBox("Observation Time")
        date_layout = QtWidgets.QVBoxLayout()
        date_row = QtWidgets.QHBoxLayout()
        self.day_in = QtWidgets.QLineEdit(); self.day_in.setPlaceholderText("Day")
        self.month_in = QtWidgets.QLineEdit(); self.month_in.setPlaceholderText("Month")
        self.year_in = QtWidgets.QLineEdit(); self.year_in.setPlaceholderText("Year")
    
        for w in [self.year_in, self.month_in, self.day_in]: w.setFixedWidth(60)
        date_row.addWidget(QtWidgets.QLabel("Date:"))
        date_row.addWidget(self.year_in); date_row.addWidget(self.month_in); date_row.addWidget(self.day_in)

        time_row = QtWidgets.QHBoxLayout()
        self.hour = QtWidgets.QLineEdit(); self.hour.setPlaceholderText("Hour")
        self.minute = QtWidgets.QLineEdit(); self.minute.setPlaceholderText("Minute")
        self.second = QtWidgets.QLineEdit(); self.second.setPlaceholderText("Second")
        for w in [self.hour, self.minute, self.second]: w.setFixedWidth(60)
        time_row.addWidget(QtWidgets.QLabel("Time (UTC):"))
        time_row.addWidget(self.hour); time_row.addWidget(self.minute); time_row.addWidget(self.second)

        date_layout.addLayout(date_row)
        date_layout.addLayout(time_row)
        date_group.setLayout(date_layout)
        right_col.addWidget(date_group)

        scroll_layout.addLayout(left_col)
        scroll_layout.addLayout(right_col)
        main_layout.addWidget(scroll_area, 11)


        self.ref_browse_btn.clicked.connect(self.browse_ref_image)
        self.browse_btn.clicked.connect(self.browse_output_dir)

        # Right panel
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        self.output_image = QtWidgets.QLabel("Output Image")
        self.output_image.setMinimumSize(QtCore.QSize(400, 400))
        self.output_image.setAlignment(QtCore.Qt.AlignCenter)
        self.future_output = QtWidgets.QTextEdit()
        self.future_output.setPlaceholderText("Simulation logs will appear here...")
        right_layout.addWidget(self.output_image)
        right_layout.addWidget(self.future_output)

        # Progress Bar 
        self.progressBar = QtWidgets.QProgressBar()
        self.progressBar.setProperty("value", 0)
        self.progressBar.setTextVisible(True)
        self.progressBar.setFormat("%p%") 
        self.progressBar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 4px;
                text-align: center;
                background-color: #2c2c2c;
                color: white;
                height: 20px;
                margin-top: 5px;
            }
            QProgressBar::chunk {
                background-color: #2196F3; /* Mavi renk */
                width: 10px;
            }
        """)
        right_layout.addWidget(self.progressBar)

        main_layout.addWidget(right_panel, 9)

        # Menü
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menufile = QtWidgets.QMenu("File")
        self.upload_action = QtWidgets.QAction("Upload Parameters")
        self.menufile.addAction(self.upload_action)
        self.menubar.addMenu(self.menufile)

        self.menuconfig = QtWidgets.QMenu("Config")
        
        # Stellarium Path 
        self.action_stellarium = QtWidgets.QAction("Stellarium Path", MainWindow)
        self.action_stellarium.triggered.connect(self.open_stellarium_config) 
        self.menuconfig.addAction(self.action_stellarium)

        # Space-Track Login
        self.action_spacetrack = QtWidgets.QAction("Space-Track Login", MainWindow)
        self.action_spacetrack.triggered.connect(self.open_spacetrack_config) 
        self.menuconfig.addAction(self.action_spacetrack)
        
        self.menubar.addMenu(self.menuconfig)

        MainWindow.setMenuBar(self.menubar)

        # Status bar
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        MainWindow.setStatusBar(self.statusbar)

        MainWindow.setCentralWidget(self.centralwidget)

        btn_layout = QtWidgets.QHBoxLayout()

        self.run_btn = QtWidgets.QPushButton("Run Simulation")
        self.run_btn.clicked.connect(self.start_simulation_thread)
        self.run_btn.setStyleSheet("background-color: #2E7D32; font-weight: bold;") # Yeşil tonu
        
        # Stop Button
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_simulation)
        self.stop_btn.setStyleSheet("background-color: #C62828; font-weight: bold;") 
        self.stop_btn.setEnabled(False) 
        
        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.stop_btn)
        left_col.addLayout(btn_layout)

        self.upload_action.triggered.connect(self.load_parameters)

        self.space_track_client = None
        self.initialize_space_track_client()

        if self.space_track_client: # Only proceed if login was successful
            self.catalog_thread = CatalogFetcherThread(self.space_track_client) 
            self.catalog_thread.result_ready.connect(self.populate_satellite_names)
            self.catalog_thread.error_occurred.connect(self.handle_catalog_error)
            self.catalog_thread.start()

            self.tle_fetch = TLEFetchExtension(self, self.space_track_client) 
            self.get_tle_btn.clicked.connect(self.tle_fetch.fetch_tle_clicked)


    def select_frame_color(self):
        """
        It opens a color palette for the user to choose the frame color.
        """
        
        initial_color = QtGui.QColor(self.selected_frame_color)
        
        # Open the color selection dialog.
        color = QColorDialog.getColor(initial=initial_color, 
                                      parent=self.centralwidget, 
                                      title="Select Frame Color")

       
        if color.isValid():
            self.selected_frame_color = color.name()
            self.frame_color_display.setStyleSheet(
                f"background-color: {self.selected_frame_color}; border: 1px solid #888888;"
            )


    def initialize_space_track_client(self):
        try:
            config = configparser.ConfigParser()
            config.read('config.ini')
            username = config['spacetrack']['username']
            password = config['spacetrack']['password']
            
            # This creates the single, persistent client for the entire app
            self.space_track_client = SpaceTrackClient(identity=username, password=password)
            self.statusbar.showMessage("Successfully connected to Space-Track.", 5000)

        except Exception as e:
            QMessageBox.critical(
                self.centralwidget,
                "Space-Track Connection Failed",
                f"Could not log in to Space-Track. Please check your config.ini and internet connection.\n\nError: {e}"
            )
            self.space_track_client = None

    def browse_sp3_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.centralwidget,
            "Select SP3 file",
            "",
            "SP3 files (*.sp3 *.SP3);;All files (*)"
        )
        if path:
            self.sp3_path_in.setText(path)

    def browse_ref_image(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.centralwidget,
            "Select Reference Image",
            "",
            # --- BU SATIRI GÜNCELLEYİN ---
            "Image files (*.fits *.png);;FITS files (*.fits);;PNG files (*.png);;All files (*)"
            # --- GÜNCELLEME BİTTİ ---
        )
        if path:
            self.ref_image_in.setText(path)

    def browse_output_dir(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self.centralwidget,
            "Select Output Directory"
        )
        if path:
            self.output_in.setText(path)

    def populate_satellite_names(self, names):
        self.sat_name_combo.clear()
        self.sat_name_combo.addItems(names)

    def handle_catalog_error(self, message):
        QtWidgets.QMessageBox.critical(self.centralwidget, "Catalog Fetch Failed", message)
    

    def load_parameters(self):
        options = QtWidgets.QFileDialog.Options()
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(None, "Select Parameter File", "", "Text Files (*.txt)", options=options)
        if fileName:
            with open(fileName, 'r') as f:
                lines = f.readlines()
                params = {}
                for line in lines:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        params[key.strip()] = value.strip()
            
            # The parameters are filled into the fields of the form.
            self.latitude_in.setText(params.get('latitude', ''))
            self.longitude_in.setText(params.get('longitude', ''))
            self.elevation_in.setText(params.get('elevation', ''))
            self.ra_in.setText(params.get('A0', ''))
            self.dec_in.setText(params.get('D0', ''))
            self.exposure_in.setText(params.get('exposure', ''))
            self.ccd_in_x.setText(params.get('ccd_x', ''))
            self.ccd_in_y.setText(params.get('ccd_y', ''))
            self.fov_in.setText(params.get('fov', ''))
            self.pixel_sixe_in.setText(params.get('pixel_size', ''))
            self.pixel_scale_in.setText(params.get('pixel_scale', ''))
            self.k_in.setText(params.get('K', ''))
            self.zero_point_in.setText(params.get('zero_point', ''))
            self.bias_in.setText(params.get('bias', ''))
            self.flat_in.setText(params.get('flat', ''))
            self.gain_in.setText(params.get('gain', ''))
            self.tle1_in.setText(params.get('tle1', ''))
            self.tle2_in.setText(params.get('tle2', ''))
            self.sp3_path_in.setText(params.get('sp3_file', ''))
            self.sp3_sat_id_in.setText(params.get('sp3_sat_id', ''))
            self.day_in.setText(params.get('day', ''))
            self.month_in.setText(params.get('month', ''))
            self.year_in.setText(params.get('year', ''))
            self.hour.setText(params.get('hour', ''))
            self.minute.setText(params.get('minute', ''))
            self.second.setText(params.get('second', ''))
            self.ccd1_1.setText(params.get('ccd1_1', ''))
            self.ccd1_2.setText(params.get('ccd1_2', ''))
            self.ccd2_1.setText(params.get('ccd2_1', ''))
            self.ccd2_2.setText(params.get('ccd2_2', ''))
            self.output_in.setText(params.get('output', ''))
            self.output_name_in.setText(params.get('output_name', ''))
            self.rotation_in.setText(params.get('rotation', ''))
            self.ref_image_in.setText(params.get('reference_image', ''))
            self.target_mag_in.setText(params.get('magnitude', '10.0'))
            self.star_min_mag_in.setText(params.get('mag_range_min', '10'))
            self.star_max_mag_in.setText(params.get('mag_range_max', '18'))
            self.bg_mag_in.setText(params.get('mag_back', '16.0'))
            self.read_noise_in.setText(params.get('read_noise', '0'))
            self.dark_current_in.setText(params.get('dark_current', '0'))
            self.seeing_in.setText(params.get('seeing', '1.2'))
            loaded_mode = params.get('mode', 'sidereal').strip().lower()
            index = self.tracking_mode_in.findText(loaded_mode, QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.tracking_mode_in.setCurrentIndex(index)
            else:
                self.tracking_mode_in.setCurrentIndex(0)


    # --- CONFIG OPERATIONS ---
    def load_config_parser(self):
        config = configparser.ConfigParser()
        if os.path.exists('config.ini'):
            config.read('config.ini')
        if 'spacetrack' not in config:
            config['spacetrack'] = {'username': '', 'password': ''}
        if 'paths' not in config:
            config['paths'] = {'stellarium_scripts': ''}
        return config

    def save_config_parser(self, config):
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

    def open_stellarium_config(self):
        config = self.load_config_parser()
        current_path = config['paths'].get('stellarium_scripts', '')
        
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self.centralwidget, "Select Stellarium Scripts Folder", current_path
        )
        
        if path:
            config['paths']['stellarium_scripts'] = path
            self.save_config_parser(config)
            QMessageBox.information(self.centralwidget, "Saved", f"Stellarium path updated:\n{path}")

    def open_spacetrack_config(self):
        config = self.load_config_parser()
        user = config['spacetrack'].get('username', '')
        pwd = config['spacetrack'].get('password', '')

        dialog = QtWidgets.QDialog(self.centralwidget)
        dialog.setWindowTitle("Space-Track Login")
        layout = QtWidgets.QVBoxLayout(dialog)
        
        u_in = QtWidgets.QLineEdit(user); u_in.setPlaceholderText("Username")
        p_in = QtWidgets.QLineEdit(pwd); p_in.setEchoMode(QLineEdit.Password); p_in.setPlaceholderText("Password")
        
        layout.addWidget(QtWidgets.QLabel("Username:")); layout.addWidget(u_in)
        layout.addWidget(QtWidgets.QLabel("Password:")); layout.addWidget(p_in)
        
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept); btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)
        
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            config['spacetrack']['username'] = u_in.text()
            config['spacetrack']['password'] = p_in.text()
            self.save_config_parser(config)
            # Try reconnecting the client with the new password.
            self.initialize_space_track_client() 
            QMessageBox.information(self.centralwidget, "Saved", "Credentials saved and client re-initialized.")

    # --- LOG AND THREAD OPERATIONS ---
    def start_simulation_thread(self):

        # If there is a thread already running or not cleaned up, clean it first.
        if hasattr(self, 'thread') and self.thread is not None:
            try:
                if self.thread.isRunning():
                    if hasattr(self, 'worker'):
                        self.worker.stop()
                    self.thread.quit()
                    self.thread.wait()
            except RuntimeError:
                pass
            del self.thread

        # Clear the log screen and write that you started the session.
        self.future_output.clear()
        self.future_output.append(f"--- NEW SESSION STARTED: {datetime.now().strftime('%H:%M:%S')} ---")
        self.run_btn.setEnabled(False) 
        self.stop_btn.setEnabled(True)
        self.progressBar.setValue(0)

        # Write parameters to a file
        try:
            temp_txt_path = self.save_params_to_temp()
        except Exception as e:
            self.future_output.append(f"[ERROR] Parameter saving failed: {e}")
            self.run_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            return

        # Start thread 
        self.thread = QThread()
        self.worker = SimulationWorker(temp_txt_path)
        self.worker.moveToThread(self.thread)

        # Signal connections
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_simulation_finished)
        self.worker.error.connect(self.on_simulation_error)
        self.worker.log_signal.connect(self.update_log_display) 
        self.worker.progress.connect(self.progressBar.setValue)
      
        # Cleaning 
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()

    def stop_simulation(self):
        if hasattr(self, 'worker'):
            self.future_output.append("\n[Stopping...] Waiting for the current step to finish...")
            self.worker.stop() 
            self.stop_btn.setEnabled(False) 

    def update_log_display(self, message):
        self.future_output.append(message)
        sb = self.future_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_simulation_finished(self, outputs):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.future_output.append("\n[SUCCESS] Simulation completed successfully.")
        
        output_image_path = outputs.get("png", "")
        if os.path.exists(output_image_path):
            pixmap = QtGui.QPixmap(output_image_path)
            w = self.output_image.width()
            h = self.output_image.height()
            if w == 0: w = 400 
            if h == 0: h = 400
            
            scaled = pixmap.scaled(w, h, QtCore.Qt.KeepAspectRatio)
            self.output_image.setPixmap(scaled)
            self.future_output.append(f"Output displayed: {output_image_path}")
        else:
            self.future_output.append("Simulation finished but output PNG not found.")

    def on_simulation_error(self, error_msg):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.future_output.append(f"\n[ERROR] Simulation crashed:\n{error_msg}")

        if hasattr(self, 'thread') and self.thread is not None:
            if self.thread.isRunning():
                self.thread.quit()
                self.thread.wait() # Thread'in tamamen kapanmasını bekle

    # --- SAVING PARAMETERS ---
    def save_params_to_temp(self):
        temp_txt_path = os.path.join(tempfile.gettempdir(), "tracklet_params.txt")
        
        # Stellarium Path'ini Config'den al
        config = self.load_config_parser()
        stel_path = config['paths'].get('stellarium_scripts', '')
        
        with open(temp_txt_path, "w") as f:
            f.write(f"latitude={self.latitude_in.text()}\n")
            f.write(f"longitude={self.longitude_in.text()}\n")
            f.write(f"elevation={self.elevation_in.text()}\n")
            f.write(f"A0={self.ra_in.text()}\n")
            f.write(f"D0={self.dec_in.text()}\n")
            f.write(f"exposure={self.exposure_in.text()}\n")
            f.write(f"ccd_x={self.ccd_in_x.text()}\n")
            f.write(f"ccd_y={self.ccd_in_y.text()}\n")
            f.write(f"fov={self.fov_in.text()}\n")
            f.write(f"pixel_size={self.pixel_sixe_in.text()}\n")
            f.write(f"pixel_scale={self.pixel_scale_in.text()}\n")
            f.write(f"K={self.k_in.text()}\n")
            f.write(f"zero_point={self.zero_point_in.text()}\n")
            f.write(f"bias={self.bias_in.text()}\n")
            f.write(f"flat={self.flat_in.text()}\n")
            f.write(f"gain={self.gain_in.text()}\n")
            f.write(f"tle1={self.tle1_in.text()}\n")
            f.write(f"tle2={self.tle2_in.text()}\n")
            f.write(f"sp3_file={self.sp3_path_in.text()}\n")
            f.write(f"sp3_sat_id={self.sp3_sat_id_in.text()}\n")
            f.write(f"day={self.day_in.text()}\n")
            f.write(f"month={self.month_in.text()}\n")
            f.write(f"year={self.year_in.text()}\n")
            f.write(f"hour={self.hour.text()}\n")
            f.write(f"minute={self.minute.text()}\n")
            f.write(f"second={self.second.text()}\n")
            f.write(f"ccd1_1={self.ccd1_1.text()}\n")
            f.write(f"ccd1_2={self.ccd1_2.text()}\n")
            f.write(f"ccd2_1={self.ccd2_1.text()}\n")
            f.write(f"ccd2_2={self.ccd2_2.text()}\n")
            f.write(f"output={self.output_in.text()}\n")
            f.write(f"output_name={self.output_name_in.text()}\n")
            f.write(f"rotation={self.rotation_in.text()}\n")
            f.write(f"reference_image={self.ref_image_in.text()}\n")
            f.write(f"mode={self.tracking_mode_in.currentText()}\n")
            f.write(f"add_frame={str(self.frame_checkbox.isChecked())}\n")
            f.write(f"frame_color={self.selected_frame_color}\n")
            f.write(f"stellarium_scripts_path={stel_path}\n")
            f.write(f"mag_range_min={self.star_min_mag_in.text()}\n")
            f.write(f"mag_range_max={self.star_max_mag_in.text()}\n")
            f.write(f"magnitude={self.target_mag_in.text()}\n")
            f.write(f"mag_back={self.bg_mag_in.text()}\n") 
            f.write(f"read_noise={self.read_noise_in.text()}\n")
            f.write(f"dark_current={self.dark_current_in.text()}\n")
            f.write(f"seeing={self.seeing_in.text()}\n")

        return temp_txt_path



if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.showMaximized()
    sys.exit(app.exec_())


