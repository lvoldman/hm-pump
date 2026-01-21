import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls.Material 2.15


// Main application window

ApplicationWindow {
    id: window                                      // main window
    visible: true                               // show window
    width: 980                                // window size
    height: 620                     // window size
    title: "SCADA Control Panel"        // window title
    background:                         // custom background
        Rectangle {                     // rounded rectangle
            color: "#12141A"  // dark background
            border.width: 10    // border width
        }               

    Material.theme: Material.Dark
    Material.primary: "#00E5FF"      // blue for primary elements
    Material.accent: "#00E5FF"          // blue for accent elements
    Material.foreground: "#E0E0E0"    // light gray for text/icons
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // 1. Панель вкладок сверху
        TabBar {
            id: mainTabBar
            Layout.fillWidth: true
            TabButton { text: "🕹 CONTROL" }
            TabButton { text: "📋 LOGS" }
        }

        // 2. Контейнер для содержимого вкладок
        StackLayout {
            currentIndex: mainTabBar.currentIndex
            Layout.fillWidth: true
            Layout.fillHeight: true

            // --- ВКЛАДКА 1: УПРАВЛЕНИЕ (Ваш текущий RowLayout) ---
            Item {
                RowLayout {
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    anchors.fill: parent            // Fill entire window
                    anchors.margins: 4
                    spacing: 2              //  Spacing between panels

                    ScrollView {
                        id: motorScroll                                 //  Scrollable area
                        Layout.preferredWidth: parent.width * 0.55   // Left panel takes 55% width
                        Layout.fillHeight: true                     // Fill height
                        clip: true                                  // important! clips (cuts) content outside
                        ScrollBar.vertical.policy: ScrollBar.AsNeeded  // vertical scrollbar as needed  
                        // ScrollBar.horizontal.policy: ScrollBar.Never     // no horizontal scrollbar
                        ScrollBar.horizontal.policy: ScrollBar.AsNeeded     // no horizontal scrollbar

                // ── Left panel - Motor ───────────────────────────────
                        Pane {

                            // Layout.preferredWidth: parent.width * 0.55
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            // width: parent.width           // important for horizontal alignment inside ScrollView
                            width: motorScroll.availableWidth  // important for horizontal alignment inside ScrollView
                            height: parent.height      // important for vertical alignment inside ScrollView
                            padding: 16                 // padding inside panel
                            Material.background: Material.CardBackground  // Material card style

                            Material.elevation: 4           // shadow depth 
                            background: Rectangle {
                                color: "#1E222D" // Цвет "стальной пластины" [cite: 10]
                                radius: 2
                                border.color: "#3A414D" // Тонкая рамка [cite: 11, 14]
                                border.width: 1
                                
                                // Внутренний градиент или блик сверху
                                Rectangle {
                                    anchors.top: parent.top
                                    width: parent.width; height: 1
                                    color: "#3D4454" // Эффект фаски
                                }
                            }



                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 12                  // spacing between elements
                                Label { 
                                    text: "MOTOR CONTROL UNIT"
                                    font.bold: true
                                    font.pixelSize: 12
                                    color: "#8A919E"
                                }
                                // Motor status
                                RowLayout {                                // motor status row            
                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 40
                                        color: "#161920"
                                        border.color: "#333"
                                        RowLayout {
                                            anchors.centerIn: parent
                                            spacing: 10
                                            Rectangle { width: 12; height: 12; radius: 6; color: motorController.isMoving ? "#00FF41" : "#2196F3" }
                                            Label { text: motorController.state; font.pixelSize: 14; font.bold: true }
                                        }
                                    
                                        // Label { text: "Motor Status:"; font.bold: true }        // bold label
                                        // Rectangle {                     // status indicator
                                        //     width: 18; height: 18; radius: 9                // circle shape
                                        //     color: {
                                        //         switch(motorController?.state ?? "OFF") {
                                        //             case "RUNNING": return "#4CAF50"
                                        //             case "WARNING": return "#FF9800"
                                        //             case "ERROR":   return "#F44336"
                                        //             case "IDLE":    return "#2196F3"
                                        //             default:        return "#757575"
                                        //         }
                                        //     }
                                        // }
                                        // Label {
                                        //     text: motorController?.state ?? "OFF"   // dynamic status text
                                        //     color: "#ffffff"
                                        // }
                                    }
                                }

                                RowLayout {                                         // motor selection row

                                    Label { text: "Select Motor by S/N:" }           // label for motor selection          
                                    ComboBox {
                                        id: motorSelector
                                        Layout.fillWidth: false                      // fill width  
                                        model: motorController.availableMotors      // model from MotorController
                                        // textRole: "sn"
                                        // model: motorController.availableMotorObjects      // model from MotorController
                                        enabled: !motorController.isMoving;
                                        // textRole: "serialNumber"                     // use serialNumber role for display
                                        currentIndex: model ? model.indexOf(motorController.currentSerialNumber) : -1        // set current index based on selected motor
                                        onActivated: (index) => {
                                            let selectedSn = model[index]                     // get selected serial number 
                                            if (selectedSn !== undefined) {         // check for valid selection
                                                motorController.currentSerialNumber = selectedSn          // update selected motor in controller
                                                console.log("Motor selected: " + selectedSn + " (index: " + index + ")")
                                            } else {
                                                console.warn("Attempted to select undefined index: " + index)
                                            }

                                            // motorController.currentSerialNumber = model[index]                      // update selected motor in controller
                                            // console.log("Port selected: " + "number " + index + " " + model[index])
                                        }
                                        font.pixelSize: 14
                                    }
                                    Label { text: "Current Limit (mA):" }
                                    SpinBox { 
                                        id: currentLimit; 
                                        from: 1; to: 500; value: 300; editable: true 
                                        onValueModified:{
                                            let val = value;
                                            if (!isNaN(val) && val !== null) {
                                                motorController.currentLimit = val;
                                            }
                                            console.log("Current limit updated to " + val + " mA")
                                        }
                                    }
                                }

                                //  Absolute move controls
                                RowLayout {                     // absolute move row
                                    Label { text: "Destination position:" }     // label for destination position
                                    TextField {                                 
                                        id: targetPos
                                        Layout.fillWidth: true                 // fill width    
                                        placeholderText: "Destination position" // placeholder text
                                        inputMethodHints: Qt.ImhDigitsOnly      // numeric input only
                                        validator: IntValidator{bottom: -100000; top: 100000}
                                    }
                                    Button {
                                        text: "Move Absolute"
                                        enabled: !motorController.isMoving
                                        onClicked: {
                                            let pos = parseInt(targetPos.text) || 0
                                            motorController.moveAbsolute(pos, velocity.value, acceleration.value, timeoutEnable.checked ? timeout.value : 0)
                                        }
                                    }
                                }

                                // Motion controls buttons
                                RowLayout {
                                    spacing: 8
                                    
                                    Button { text: "◀ Backward";  enabled: !motorController.isMoving; onClicked: { motorController.moveBackward(velocity.value, acceleration.value, timeoutEnable.checked ? timeout.value : 0); console.log("Backward pressed") } }
                                    Button { text: "■ STOP";      highlighted: true; Material.background: Material.Red;  onClicked: { motorController.stop(); console.log("Stop pressed");}}
                                    Button { text: "Forward ▶"; enabled: !motorController.isMoving; onClicked: { motorController.moveForward(velocity.value, acceleration.value, timeoutEnable.checked ? timeout.value : 0); console.log("Forward pressed") }}
                                    Button { text: "Home"; enabled: !motorController.isMoving; onClicked: { motorController.home(); console.log("Home pressed") } }
                                }

                                GridLayout {
                                    columns: 2
                                    Layout.fillWidth: true
                                    enabled: !motorController.isMoving   // Disable while motor is moving
                                    opacity: enabled ? 1.0 : 0.5 // Visual feedback when disabled
                                    Behavior on opacity { NumberAnimation { duration: 200 } }

                                    Label { text: "Velocity:" }
                                    SpinBox { id: velocity; from: 1; to: 5000; value: 1000; editable: true }

                                    Label { text: "Acceleration:" }
                                    SpinBox { id: acceleration; from: 10; to: 10000; value: 2000; editable: true }
                                }

                                Rectangle { Layout.fillWidth: true; height: 1; color: "#444" }

                                // Current values
                                GridLayout {
                                    columns: 2
                                    Label { text: "Current position:" }
                                    // TextField { readOnly: true; text: motorController.currentMotor?.position ?? "—" }
                                    TextField { readOnly: true; text: motorController?.position ?? "—" }

                                    Label { text: "Running time:" }
                                    TextField { id: runtimeDisplay; readOnly: true; text: "00:00:00" }
                                }

                                Timer {
                                    id: runningTimer
                                    interval: 1000 // 1 second
                                    // running: motorController.isMoving // Timer runs while the motor is moving
                                    running: motorController.state === "RUNNING"  //
                                    repeat: true
                                    
                                    property int seconds: 0

                                    onTriggered: {          // Increment runtime every second
                                        seconds++;
                                        runtimeDisplay.text = formatTime(seconds);
                                    }
                                    
                                    // Reset when movement starts
                                    onRunningChanged: {         // Reset seconds when motor starts moving
                                        if (running) {
                                                seconds = 0; 
                                            runtimeDisplay.text = "00:00:00";
                                        }
                                    }

                                    function formatTime(s) {
                                        let h = Math.floor(s / 3600).toString().padStart(2, '0');
                                        let m = Math.floor((s % 3600) / 60).toString().padStart(2, '0');
                                        let sec = (s % 60).toString().padStart(2, '0');
                                        return h + ":" + m + ":" + sec;
                                    }
                                }

                                CheckBox {
                                    id: timeoutEnable
                                    text: "Enable timeout"
                                }

                                RowLayout {
                                    enabled: timeoutEnable.checked
                                    Label { text: "Timeout (s):" }
                                    SpinBox { id: timeout; from: 1; to: 3600; value: 30; editable: true }
                                }
                            }
                        }

                    }


                    // ── Правая панель: Scale ──────────────────────────────
                    Pane {
                        id: scalePanel
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        background: Rectangle {
                            color: "#1E222D" // Цвет "стальной пластины" [cite: 10]
                            radius: 4
                            border.color: "#3A414D" // Тонкая рамка [cite: 11, 14]
                            border.width: 1
                            
                            // Внутренний градиент или блик сверху
                            Rectangle {
                                anchors.top: parent.top
                                width: parent.width; height: 1
                                color: "#3D4454" // Эффект фаски
                            }
                        }


                        ColumnLayout {
                            // width: scrollView.width   // ← neccesary for horizontal alignment
                            // height: scrollView.height // ← do not set height, if want it expand naturally
                            spacing: 16
                            anchors.fill: parent
                            anchors.margins: 12
                            Label { text: "MEASUREMENT UNIT"; font.bold: true; font.pixelSize: 12; color: "#8A919E" }
                            RowLayout {
                                Label { text: "Scale Status:"; font.bold: true }
                                Rectangle {
                                    width: 18; height: 18; radius: 9
                                    color: scaleController.isConnected ? "#4CAF50" : "#F44336"
                                }
                                Label { text: scaleController.isConnected ? "CONNECTED" : "DISCONNECTED" }
                            }
                            
                            Label { text: "Select Port:" }
                            ComboBox {
                                Layout.fillWidth: true
                                model: scaleController.availablePorts // model from ScaleController
                                // currentIndex: model.indexOf(scaleController.currentSerialPort)
                                currentIndex: model ? model.indexOf(scaleController.currentSerialPort) : -1   // handle empty model case, if no scales found
                                onActivated: (index) => {
                                    scaleController.update_serial_port(model[index])
                                    scaleController.connect()
                                    console.log("Port selected: " + "number " + index + " " + model[index])
                                }
                            }
                            Label { text: "Weight:" }
                            Rectangle {
                                Layout.fillWidth: true
                                height: 80
                                color: "#0A0B0E" // Почти черный "экран"
                                border.color: "#444"
                                radius: 4

                                Label {
                                    anchors.centerIn: parent
                                    text: scaleController.weight.toFixed(2) + " kg"
                                    color: "#00E5FF" // Цифровой голубой
                                    font.pixelSize: 42
                                    font.family: "Courier New"
                                }
                            }
                            // TextField {
                            //     id: weightDisplay
                            //     Layout.fillWidth: true
                            //     readOnly: true
                            //     color: "#00E5FF" // Neon blue color for weight display
                            //     font.family: "Courier New" // Industrial style
                            //     font.pixelSize: 32
                            //     background: Rectangle { color: "#0A0C10"; radius: 2 }
                            //     horizontalAlignment: Text.AlignHCenter
                            //     text: scaleController.weight ? scaleController.weight.toFixed(2) + " kg" : "—"
                            // }

                            Label { text: "Power=W/T:" }
                            Rectangle {
                                Layout.fillWidth: true
                                height: 60
                                color: "#0A0B0E"
                                border.color: "#444"
                                Label {
                                    anchors.centerIn: parent
                                    text: "Rate of Change (ROC): " + (motorController.isMoving ? (scaleController.weight / runningTimer.seconds).toFixed(2) : "0.00") + " kg/s"
                                    color: "#FFA500" // Оранжевый для производных данных
                                    font.pixelSize: 20
                                }
                            }
                            // TextField {
                            //     Layout.fillWidth: true
                            //     readOnly: true
                            //     color: "#00E5FF" // Neon blue color for weight display
                            //     font.family: "Courier New" // Industrial style
                            //     font.pixelSize: 32
                            //     background: Rectangle { color: "#0A0C10"; radius: 2 }
                            //     // text: "Rate of Change by Weight (ROC) - Weight/Time"
                            //     text: {
                            //         if ( motorController.isMoving && scaleController.weight !== undefined && runningTimer.seconds > 0) {
                            //             let power = scaleController.weight / runningTimer.seconds; // kg/s
                            //             return power.toFixed(2) + " kg/s"
                            //         } else {
                            //             return "Rate of Change by Weight (ROC) - Weight/Time"
                            //         }
                            //     }
                            // }

                            Item { Layout.fillHeight: true }

                            RowLayout {
                                Label { text: "Poll interval (ms):" }
                                SpinBox {
                                    from: 50; to: 5000; value: 100; stepSize: 50; editable: true
                                    onValueModified:{
                                        let val = value / 1000;
                                        if (!isNaN(val) && val !== null) {
                                            scaleController.update_poll_interval(val); // convert ms to s
                                        }
                                        // scaleController.update_poll_interval(value / 1000)   // convert ms to s
                                        console.log("Poll interval updated to " + value + " ms")
                                    } 
                                }
                            }
                        }
                    }
                }
            }
            Item {
                Rectangle {
                    anchors.fill: parent
                    color: "#0F1117"
                    Label {
                        anchors.centerIn: parent
                        text: "System Logs will be here..."
                        color: "#8A919E"
                    }
                }    
            }
        }
    }
    // Connections {
    //     // Call this method from Python side to update target motor when selection changes
    //     target: motorController.get_motor_by_index(motorSelector.currentIndex)

    //     onPositionChanged: (p) => { 
    //         console.log("Position updated to: " + p);}
    // }
}
