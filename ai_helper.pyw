#!/usr/bin/env python3

import json
import markdown
import openai
import os
import pickle
import random
import re
import string
import sys
import time
import traceback
from datetime import datetime
from dotenv import load_dotenv
from platformdirs import user_config_dir
import tiktoken

from PyQt6 import QtWidgets
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from PyQt6.QtWidgets import QApplication, QListWidget, QAbstractItemView, QSizePolicy, QMenu, QMessageBox, QInputDialog, QLineEdit, QDialog, QPlainTextEdit, QVBoxLayout, QWidget


from ai_helper_gui import Ui_MainWidget

# python -m venv .python-env/generativeAI
# source ~/.python-env/generativeAI/bin/activate 
# pip install markdown openai tiktoken pyqt6 PyQt6-WebEngine python-dotenv platformdirs pyinstaller
# pyinstaller --add-data --noconsole --onefile ai_helper.pyw

class ChatSession:
    def __init__(self):
        self.messages = []
        self.title = "new"
        self.str_fixed_prompt = ""
        self.bool_atomic_mode = False

    def append_message(self, role, content, model="", total_token = "", input_token="", output_token="", elapsed_time="", temperature="", top_p="", n="", max_tokens="", price="", atomic_mode=""):
        if self.title == "new":
            self.title = str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        message = {
            "role": str(role), 
            "content": str(content),
            "model": str(model),
            "total_token": str(total_token),
            "input_token": str(input_token),
            "output_token": str(output_token),
            "elapsed_time": str(elapsed_time),
            "temperature":  str(temperature),
            "top_p": str(top_p),
            "n": str(n),
            "max_tokens": str(max_tokens),
            "price": str(price),
            "atomic": str(atomic_mode)
            }

        self.messages.append(message)
    
    def get_title(self):
        return self.title

    def set_title(self, str_title):
        self.title = str(str_title)
    
    def get_all_messages(self):    
        return self.messages
    
    def get_filtered_messages(self):    
        return [{"role": message["role"], "content": message["content"]} for message in self.messages]

    def isEmpty(self):
        if len(self.messages) > 0:
            return False
        return True
    
    def set_fixed_prompt(self, str_prompt):
        self.str_fixed_prompt = str(str_prompt)

    def get_fixed_prompt(self):
        return self.str_fixed_prompt
    
    def enable_atomic_mode(self):
        self.bool_atomic_mode = True

    def disable_atomic_mode(self):
        self.bool_atomic_mode = False

    def get_atomic_mode(self):
        return self.bool_atomic_mode

class AI_Helper(QtWidgets.QWidget):
    def __init__(self, parent=None):        
        super(AI_Helper, self).__init__(parent)        
        self.mainWidget = Ui_MainWidget()
        self.mainWidget.setupUi(self)
        self.setGeometry(100, 100, 1280, 1024)
        
        self.bool_debug_mode = False

        self.initialize_variables()        

        self.config_dir = user_config_dir("ai_helper")
        self.config_file = os.path.join(self.config_dir, "history.pkl")
        
        if not os.path.exists(self.config_dir):            
            os.makedirs(self.config_dir)
        
        if os.path.exists(self.config_file):              
            with open(self.config_file, 'rb') as f:
                loaded_list = pickle.load(f)
                self.list_chat_messages.extend(loaded_list)
        
        self.initial_config()        
        self.setup_connections()

        self.list_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        self.log_message("INFO", "Initializing application.")  
        self.log_message("DEBUG", "History file:" + self.config_file)  
        
        if os.path.exists(self.config_file):
            self.log_message("INFO", "Loading file:" + self.config_file)
        else:
            self.log_message("INFO", "File \"" + self.config_file + "\" not found.")  

    def setup_connections(self):
        self.mainWidget.clearButton.clicked.connect(self.confirm_clear)
        self.mainWidget.sendButton.clicked.connect(self.send_message) 
        self.mainWidget.tabWidget.currentChanged.connect(self.tab_changed)
        self.mainWidget.modelComboBox.currentIndexChanged.connect(self.model_changed)
        self.mainWidget.historyWidget.currentRowChanged.connect(self.update_chat_message)
        self.mainWidget.newButton.clicked.connect(self.new_chat)
        self.mainWidget.infoCheckBox.stateChanged.connect(self.informational_mode)
        self.mainWidget.webEngineView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.mainWidget.webEngineView.customContextMenuRequested.connect(self.showWebEngineViewCustomContextMenu)

    def showWebEngineViewCustomContextMenu(self, position):
        contextMenu = QMenu(self)
        
        # Obtener referencia a las acciones de página
        pageAction = self.mainWidget.webEngineView.pageAction
 
        customAction = QAction("Show source ", self)
        customAction.triggered.connect(self.show_source_code)
        reloadAction = QAction("Reload", self)
        reloadAction.triggered.connect(self.update_chat)
        
        # Agregar acciones estándar del navegador
        contextMenu.addAction(pageAction(QWebEnginePage.WebAction.Copy))
        contextMenu.addAction(reloadAction)
        contextMenu.addAction(customAction)
        
        # Mostrar el menú
        contextMenu.exec( self.mainWidget.webEngineView.mapToGlobal(position))

    def show_source_code(self, parent=None):
        if not isinstance(parent, QWidget):
            parent = None
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("HTML Source Code")
        dialog.setModal(True)
        dialog.resize(1024, 800)

        # Configurar el layout
        layout = QVBoxLayout(dialog)

        # Crear el editor de texto
        text_editor = QPlainTextEdit()
        text_editor.setReadOnly(True)

        # Configurar una fuente monoespaciada
        font = QFont("Courier New")
        font.setPointSize(12)
        text_editor.setFont(font)

        # Establecer el texto
        text_editor.setPlainText(self.create_html())

        # Agregar el editor al layout
        layout.addWidget(text_editor)

        # Configurar las flags de la ventana
        dialog.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )

        # Mostrar la ventana
        dialog.exec()

    def informational_mode(self):
        if self.mainWidget.infoCheckBox.isChecked():
            self.bool_informational_mode = True
        else:
            self.bool_informational_mode = False

        self.update_chat()

    def initialize_variables(self):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")

        self.str_history_filename = "ai_helper.pkl"
        self.list_models = []
        self.list_chat_messages = []        
        self.bool_informational_mode = False

        dict_model = {
            "name": "GPT-4o",
            "model": "chatgpt-4o-latest",
            "max_tokens": 16384,
            "context_window": 128000,
            "encoding": "o200k_base",
            "tiktoken": "gpt-4o",
            "input_price": 2.5,
            "output_price": 10
        }
        
        dict_model_default = dict_model

        self.list_models.append(dict_model)

        dict_model = {
            "name": "GPT-4o mini",
            "model": "gpt-4o-mini",
            "max_tokens": 16384,
            "context_window": 128000, 
            "encoding": "o200k_base",
            "tiktoken": "gpt-4o",            
            "input_price": 0.150,
            "output_price": 0.6      
        }        

        self.list_models.append(dict_model)

        dict_model = {
            "name": "o1",
            "model": "o1",
            "max_tokens": 100000, 
            "context_window": 200000,
            "encoding": "o200k_base",
            "tiktoken": "gpt-4o-",
            "encoding": "o200k_base",
            "tiktoken": "gpt-4o",
            "input_price": 15,
            "output_price": 60         
        }

        self.list_models.append(dict_model)        

        self.current_dict_config = {
            "model": dict_model_default,
            "temperature": 0.7,
            "n": 1,
            "top_p": 1
            
        }       

    def new_chat(self):
        self.chat_messages = ChatSession()
        self.list_chat_messages.insert(0, self.chat_messages)
        self.update_history()
        self.update_chat()
        self.mainWidget.historyWidget.setCurrentRow(0)

    def update_chat_message(self, index):        
        if index == -1:
            self.mainWidget.historyWidget.setCurrentRow(0)
        else:
            self.chat_messages = self.list_chat_messages[index]            

        self.update_chat()

    def initial_config(self):

        self.mainWidget.logTableWidget.setColumnCount(3)
        self.mainWidget.logTableWidget.horizontalHeader().setVisible(False)
        self.mainWidget.logTableWidget.verticalHeader().setVisible(False)
        self.mainWidget.logTableWidget.horizontalHeader().setStretchLastSection(True)
        self.mainWidget.logTableWidget.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.mainWidget.logTableWidget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.mainWidget.logTableWidget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        self.mainWidget.webEngineView.settings().setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
        self.mainWidget.webEngineView.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        self.mainWidget.webEngineView.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        self.mainWidget.webEngineView.settings().setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)

        self.mainWidget.temperatureDoubleSpinBox.setValue(self.current_dict_config["temperature"])
        self.mainWidget.temperatureDoubleSpinBox.setSingleStep(0.1)        
        self.mainWidget.temperatureDoubleSpinBox.setMinimum(0)
        self.mainWidget.temperatureDoubleSpinBox.setMaximum(2.0)
        self.mainWidget.temperatureDoubleSpinBox.setToolTip("What sampling temperature to use, between 0 and 2. Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic. We generally recommend altering this or top_p but not both.")

        self.mainWidget.top_pDoubleSpinBox.setValue(self.current_dict_config["top_p"])
        self.mainWidget.top_pDoubleSpinBox.setSingleStep(0.1)        
        self.mainWidget.top_pDoubleSpinBox.setMinimum(0)
        self.mainWidget.top_pDoubleSpinBox.setMaximum(1.0)
        self.mainWidget.top_pDoubleSpinBox.setToolTip("An alternative to sampling with temperature, called nucleus sampling, where the model considers the results of the tokens with top_p probability mass. So 0.1 means only the tokens comprising the top 10% probability mass are considered. We generally recommend altering this or temperature but not both.")

        self.mainWidget.nSpinBox.setValue(self.current_dict_config["n"])
        self.mainWidget.nSpinBox.setSingleStep(1)        
        self.mainWidget.nSpinBox.setMinimum(1)
        self.mainWidget.nSpinBox.setMaximum(5)
        self.mainWidget.nSpinBox.setToolTip("How many chat completion choices to generate for each input message. Note that you will be charged based on the number of generated tokens across all of the choices. Keep n as 1 to minimize costs.")

        for dict_model in self.list_models:
            model_name = dict_model["name"]
            self.mainWidget.modelComboBox.addItem(model_name)

        self.mainWidget.historyWidget.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
       
        self.mainWidget.historyWidget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.mainWidget.historyWidget.setUniformItemSizes(True)
        self.mainWidget.historyWidget.setCurrentRow(0)
        self.mainWidget.historyWidget.setStyleSheet("""QListWidget::item { height: 30px; padding: 5px; } """)
        self.mainWidget.historyWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.mainWidget.historyWidget.customContextMenuRequested.connect(self.show_context_menu)

        self.mainWidget.maxTokensSpinBox.setSingleStep(100)
        self.mainWidget.maxTokensSpinBox.setMinimum(0)
        self.mainWidget.maxTokensSpinBox.setMaximum(int(self.current_dict_config["model"]["max_tokens"]))
        self.mainWidget.maxTokensSpinBox.setValue(int(self.current_dict_config["model"]["max_tokens"]))  

        self.mainWidget.modelComboBox.setCurrentText(self.current_dict_config["model"]["name"])

        if self.bool_informational_mode:
            self.mainWidget.infoCheckBox.setChecked(True)
        else:
            self.mainWidget.infoCheckBox.setChecked(False)

        self.update_history()
        self.new_chat()
        self.update_chat()

    def show_context_menu(self, position):
        menu = QMenu()

        edit_action = menu.addAction("Editar")
        delete_action = menu.addAction("Eliminar")
      
        int_index = self.mainWidget.historyWidget.currentRow()                
        action = menu.exec(self.mainWidget.historyWidget.mapToGlobal(position))

        if int_index != -1:
            if action == delete_action:        
                reply = QMessageBox.question(
                    None, 
                    "Confirm Deletion",
                    "Are you sure you want to delete this item?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:                    
                    self.list_chat_messages.pop(int_index)                     

                if len(self.list_chat_messages) > 0:
                    if len(self.list_chat_messages) <= int_index:                  
                        self.mainWidget.historyWidget.setCurrentRow(int_index - 1 )

                self.save_history()

            elif action == edit_action:                                        
                current_item = self.mainWidget.historyWidget.item(int_index)
                if current_item:                    
                    text, ok = QInputDialog.getText(
                        None,
                        "Editar mensaje",
                        "Modificar texto:",
                        QLineEdit.EchoMode.Normal,
                        self.list_chat_messages[int_index].get_title()
                    )
                                
                    if ok and text.strip():                        
                        current_item.setText(text)
                        self.list_chat_messages[int_index].set_title(text)

        
        if  int_index  == - 1:
            self.mainWidget.historyWidget.setCurrentRow(0)        

        if len(self.list_chat_messages) > 0:
            self.update_history()
        else:
            self.new_chat()

    def update_history(self):   
        int_index = self.mainWidget.historyWidget.currentRow()        

        self.mainWidget.historyWidget.clear()        
        
        for chat in self.list_chat_messages:
            self.mainWidget.historyWidget.addItem(chat.get_title())
        
        self.mainWidget.historyWidget.setCurrentRow(int_index)

    def model_changed(self, index):
        self.current_dict_config["model"] = self.list_models[index]
        self.mainWidget.maxTokensSpinBox.setMaximum(int(self.current_dict_config["model"]["max_tokens"]))
        self.mainWidget.maxTokensSpinBox.setValue(int(self.current_dict_config["model"]["max_tokens"]))

    def tab_changed(self, index):
        self.mainWidget.logTableWidget.resizeColumnsToContents()
        self.mainWidget.logTableWidget.resizeRowsToContents()
        self.update_chat()

    def update_chat(self):
        str_html = self.create_html()
        self.mainWidget.webEngineView.setHtml(str_html)
        self.mainWidget.webEngineView.update()

        str_fixed = self.chat_messages.get_fixed_prompt()        
        self.mainWidget.fixedTextEdit.setText(str_fixed)

        if self.chat_messages.get_atomic_mode():
            self.mainWidget.atomicCheckBox.setChecked(True)
        else:
            self.mainWidget.atomicCheckBox.setChecked(False)

    def log_message(self, str_level, str_message):            
        str_timestamp = str(datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f')[:-3])
        str_message = str(str_message)
        str_level = str(str_level)

        if str_level not in self.list_log_levels:
            str_level = "DEBUG"
        
        row = self.mainWidget.logTableWidget.rowCount()

        self.mainWidget.logTableWidget.insertRow(row)
        self.mainWidget.logTableWidget.setItem(row, 0, QtWidgets.QTableWidgetItem(str_timestamp))
        self.mainWidget.logTableWidget.setItem(row, 1, QtWidgets.QTableWidgetItem(str_level)) 
        self.mainWidget.logTableWidget.setItem(row, 2, QtWidgets.QTableWidgetItem(str_message))

        self.mainWidget.logTableWidget.update()
        self.mainWidget.logTableWidget.resizeColumnsToContents()
        self.mainWidget.logTableWidget.resizeRowsToContents()

        self.mainWidget.logTableWidget.scrollToBottom()
  
    def confirm_clear(self):
        if self.mainWidget.textEdit.toPlainText() != "":            
            reply = QtWidgets.QMessageBox.question(self, 'Confirm Clear', "Are you sure you want to clear the text?", QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No, QtWidgets.QMessageBox.StandardButton.No)
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.mainWidget.textEdit.clear()

    def create_html(self):

        font_family = self.mainWidget.textEdit.font().family()
        font_size = self.mainWidget.textEdit.font().pointSize()

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
            * {
               font-family: system-ui, -apple-system, Calibri, 'Segoe UI', Ubuntu, 'Liberation Sans', sans-serif;
               text-rendering: optimizeLegibility;
               -webkit-font-smoothing: antialiased;
               font-size: 12pt;
            }
            body {                
                background-color: #f5f5f4;                
                line-height: 1.5;
                margin: 0;
                padding: 15px;
            }
            pre {
                background-color: #f6f8fa;
                padding: 16px;
                border-radius: 6px;
                overflow-x: auto;
            }

            code {
                font-family: monospace;
            }

            ul {
                padding-left: 20px !important;
                margin: 0 0 10px 0 !important;
                list-style-type: disc !important;
            }
            
            ul ul {
                margin: 5px 0 5px 20px !important;
                list-style-type: circle !important;
            }
            
            ul ul ul {
                list-style-type: square !important;
            }
            
            li {
                margin: 5px 0 !important;
                display: list-item !important;
                padding-left: 5px !important;
            }
            
            .message-bubble ul {
                margin-top: 10px !important;
            }
            
            .message-bubble li {
                line-height: 1.5 !important;
            }
            
            .user-name {        
                background-color: #e8e8e8;
                padding: 10px;
                border-radius: 16px;
                width: fit-content;
                max-width: 95%;
                margin-left: auto;
                margin-bottom: 10px;
                word-wrap: break-word;
                overflow-wrap: anywhere;
                white-space: normal;
            }
            
            .message-bubble {
                background-color: white;
                padding: 10px;
                border-radius: 16px;                          
                width: fit-content;
                max-width: 95%;
                margin-right: auto;   
                margin-bottom: 20px;               
                word-wrap: break-word;
                overflow-wrap: anywhere;
                white-space: normal;
            }

            .message-title {
                position: relative;
                top: 5px;
                right: 10px;
                font-size: 9pt;
                color: #000000;               
                margin-bottom: 20px;
                text-align: right;
            }
            </style>
        </head>
        <body>
        """
        
        for message in self.chat_messages.get_all_messages():
            content = message["content"]            

            if message["role"] == "user":
                if self.is_markdown(content):
                    content = self.markdown_to_html(content)                   
                else:                    
                    content = content.replace('\n', '<br>')
                
                html += f'<div class="user-name">{content}</div>'

            elif message["role"] == "assistant":
                if self.is_markdown(content):
                    content = self.markdown_to_html(content)                
                else:                    
                    content = content.replace('\n', '<br>')
                
                if self.bool_informational_mode:
                    model = message["model"]
                    total_token = message["total_token"]
                    input_token = message["input_token"]
                    output_token = message["output_token"]
                    elapsed_time = message["elapsed_time"]
                    temperature =  message["temperature"]
                    top_p =  message["top_p"]
                    n =  message["n"]
                    price =  message["price"]
                    atomic_mode = message["atomic"]

                    str_tokens = "Tokens: " + str(total_token) + " (Input: " + str(input_token) + ", Output: " + str(output_token) + ")"
                    
                    html += '<div class="message-bubble">'
                    html += '<div class="message-title">'                    
                    html += 'Model: ' + model + '<br>'
                    html += str_tokens  + '<br>'
                    html += "Time elapsed: " + str(elapsed_time) + " seconds" + '<br>'
                    html += 'Temperature: ' + str(temperature) + ' Top P: ' + str(top_p) + ' N: ' + str(n) + '<br>'
                    html += 'Atomic Mode: ' + str(atomic_mode) +'<br>'
                    html += 'Price: ' + str(price) + '$'                    
                    html += '</div>' +  content + '</div>'
                else:
                    html += f'<div class="message-bubble">{content}</div>'

        html += "</body></html>"

        return html

    def is_markdown(self, text):
        """
        Detector mejorado de markdown para PyQt6
        """
        patterns = [
            r"^#{1,6}\s",                    # headers
            r"^\s*[-*]\s",                   # listas
            r"^\s+[-*]\s",                   # listas anidadas (con indentación)
            r"\[.*?\]\(.*?\)",               # links
            r"!\[.*?\]\(.*?\)",              # images
            r"(?<![\*_])[\*_](?![\*_]).*?(?<![\*_])[\*_](?![\*_])",  # italic
            r"(?<![\*_])[\*_]{2}(?![\*_]).*?(?<![\*_])[\*_]{2}(?![\*_])",  # bold
        ]
        return any(re.search(p, text, re.MULTILINE) for p in patterns)

    def send_message(self):
        str_fixed = self.mainWidget.fixedTextEdit.toMarkdown()        
        str_textEdit = self.mainWidget.textEdit.toMarkdown()        

        str_content = str_fixed + "\n" + str_textEdit

        if not self.mainWidget.atomicCheckBox.isChecked():
            self.chat_messages.disable_atomic_mode()
        else:
            self.chat_messages.enable_atomic_mode()

        if str_textEdit != "":

            self.chat_messages.append_message("user", str_content)
            
            self.mainWidget.textEdit.setDisabled(True)
            self.mainWidget.sendButton.setDisabled(True)

            self.update_chat()                                   

            if str_fixed:
                self.chat_messages.set_fixed_prompt(str_fixed)


            if not self.mainWidget.atomicCheckBox.isChecked():
                if self.get_chatgpt_response(self.chat_messages):
                    self.mainWidget.textEdit.clear()

            else:
                tmp_chat_messages = ChatSession()
                tmp_chat_messages.append_message("user", str_content)

                if self.get_chatgpt_response(tmp_chat_messages):
                    self.mainWidget.textEdit.clear()

            
            self.update_chat()            
            self.update_history()
            self.mainWidget.textEdit.setDisabled(False)
            self.mainWidget.sendButton.setDisabled(False)
            self.mainWidget.textEdit.setFocus()
            self.save_history()

    def save_history(self):
        tmp_chat_messages = []

        if len(self.list_chat_messages) > 0:            
            for chat in self.list_chat_messages:                
                if not chat.isEmpty():
                    tmp_chat_messages.append(chat)
                    

        if tmp_chat_messages != []:
            with open(self.config_file, 'wb') as f:
                pickle.dump(tmp_chat_messages, f)                

    def closeEvent(self, event):
        self.save_history()
        super().closeEvent(event)

    def get_chatgpt_response(self, obj_chat_messages):
        try:            
            openai_api_key = os.getenv("OPENAI_API_KEY")

            if not openai_api_key:
                self.log_message("ERROR", "OPENAI_API_KEY environment variable is not set")
                QtWidgets.QMessageBox.critical(self, "Error", "OPENAI_API_KEY environment variable is not set")
                return False

            else:
                client = openai.OpenAI()

                self.log_message("INFO", "Getting response from ChatGPT.")                                

                int_max_tokens = self.mainWidget.maxTokensSpinBox.value()
                float_temperature = self.mainWidget.temperatureDoubleSpinBox.value()
                float_top_p = self.mainWidget.top_pDoubleSpinBox.value()
                int_n = self.mainWidget.nSpinBox.value()
                str_model = self.current_dict_config["model"]["model"]
                if self.mainWidget.atomicCheckBox.isChecked():
                    str_atomic_mode = "enable"
                else:
                    str_atomic_mode = "disable"

                self.log_message("DEBUG", "Parameters: \nModel: " + str(str_model) + "\nTemperature: " + str(float_temperature) + "\nMax tokens: " + str(int_max_tokens))                

                start = time.time()

                completion = client.chat.completions.create(
                        model=str_model,
                        messages=obj_chat_messages.get_filtered_messages(),
                        max_tokens=int_max_tokens,
                        temperature=float_temperature,
                        frequency_penalty=0,
                        presence_penalty=0,
                        n=int(int_n),
                        top_p=float(float_top_p),
                )                               

                if self.bool_debug_mode:
                    str_timestamp = str(datetime.now().strftime('%Y%m%d%H%M%S'))
                    str_random = str(''.join(random.choices(string.ascii_letters + string.digits, k=10)))                
                    str_filename = str_timestamp + "." + str_random + ".json"
                    str_filename  = os.path.join(self.config_dir, str_filename)
                    with open(str_filename, 'w') as f:
                        json.dump(obj_chat_messages.get_filtered_messages(), f, indent=4)
                        json.dump(json.loads(completion.model_dump_json()), f, indent=4)


                end = time.time()
                time_elapsed = end - start
                timerounded = round(time_elapsed, 3)

                self.log_message("INFO", "Response received from ChatGPT.")
                self.log_message("DEBUG", "Time elapsed: " + str(timerounded) + " seconds")

                if completion is None:
                    self.log_message("ERROR", "An error has occurred")
                    QtWidgets.QMessageBox.critical(self, "Error", "An error has occurred")

                else:                     
                    self.log_message("DEBUG", "Number of choices in response: " + str(len(completion.choices)))

                    if len(completion.choices) > 0:
                        for choice in completion.choices:
                            int_index = completion.choices.index(choice)
                            self.log_message("DEBUG", "Finish reason for choice " + str(int_index) + ": " + str(choice.finish_reason))                    
                    
                            str_content = str(choice.message.content)
                            str_model_name = str(self.current_dict_config["model"]["name"])

                            int_total = (completion.usage.total_tokens)
                            int_prompt = (completion.usage.prompt_tokens)
                            int_output = (completion.usage.completion_tokens)

                            float_input_price  = ((float(int_prompt) * float(self.current_dict_config["model"]["input_price"])) / float(1000000))
                            float_output_price = ((float(int_output) * float(self.current_dict_config["model"]["output_price"])) / float(1000000))
                            total_price = float_input_price + float_output_price 
                            str_total_price = str(round(total_price, 10))
                            
                            self.chat_messages.append_message("assistant", str_content, str_model_name, str(int_total), str(int_prompt), str(int_output), str(timerounded), float_temperature, float_top_p, int_n, int_max_tokens, str_total_price, str_atomic_mode)

                    str_tokens = "Tokens: " + str(int_total) + " (Prompt: " + str(int_prompt) + ", Output: " + str(int_output) + ")"
                    self.log_message("DEBUG", str_tokens)                    

            return True

        except openai.NotFoundError as e:     
            error_type = type(e).__name__
            error_message = getattr(e, 'message', str(e))
            self.log_message("ERROR", f"{error_type}: {error_message}")
                    
            tb_info = traceback.format_exc()
            self.log_message("DEBUG", f"Full traceback:\n{tb_info}")

            QtWidgets.QMessageBox.critical(self,"OpenAI API Error", f"An error occurred while processing your request:\n{error_type}: {error_message}"   )

            return False
        
        except openai.RateLimitError as e:     
            error_type = type(e).__name__
            error_message = getattr(e, 'message', str(e))
            self.log_message("ERROR", f"{error_type}: {error_message}")
                    
            tb_info = traceback.format_exc()
            self.log_message("DEBUG", f"Full traceback:\n{tb_info}")

            QtWidgets.QMessageBox.critical(self,"OpenAI API Error", f"An error occurred while processing your request:\n{error_type}: {error_message}"   )

            return False

        except Exception as e:
            error_type = type(e).__name__
            error_message = getattr(e, 'message', str(e))
            self.log_message("ERROR", f"{error_type}: {error_message}")
                    
            tb_info = traceback.format_exc()
            self.log_message("DEBUG", f"Full traceback:\n{tb_info}")

            QtWidgets.QMessageBox.critical(self,"Error", f"An error occurred while processing your request:\n{error_type}: {error_message}"   )

            return False


    def markdown_to_html(self, text):
        # Preprocesar el texto para mantener la indentación
        lines = text.split('\n')
        processed_lines = []
        list_level = 0

        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)

            if stripped.startswith('- ') or stripped.startswith('* '):
                # Calcular el nivel de indentación basado en espacios
                list_level = indent // 2
                # Asegurar que usamos el número correcto de espacios
                line = ('  ' * list_level) + stripped

            processed_lines.append(line)

        text = '\n'.join(processed_lines)

        # Convertir a HTML
        html = markdown.markdown(
            text,
            extensions=['fenced_code', 'tables', 'nl2br', 'codehilite', 'sane_lists'],
            output_format='html5'
        )

        return html


if __name__ == "__main__":

    current_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(current_dir, 'three-dots.png')

    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QIcon(icon_path))
    AI_Helper_app = AI_Helper()
    AI_Helper_app.show()
    sys.exit(app.exec())





