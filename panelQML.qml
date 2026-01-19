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
            color: "#0F1117"  // dark background
            border.width: 10    // border width
        }               

    Material.theme: Material.Dark
    Material.primary: "#1976D2"      // blue for primary elements
    Material.accent: "#1976D2"          // blue for accent elements
    Material.foreground: "#E0E0E0"    // light gray for text/icons
    
    RowLayout {
        anchors.fill: parent            // Fill entire window
        spacing: 1              //  Spacing between panels

        ScrollView {
            id: scrollView                                 //  Scrollable area
            Layout.preferredWidth: parent.width * 0.55   // Left panel takes 55% width
            Layout.fillHeight: true                     // Fill height
            clip: true                                  // important! clips (cuts) content outside

        // ── Left panel - Motor ───────────────────────────────
            Pane {

                // Layout.preferredWidth: parent.width * 0.55
                // Layout.fillHeight: true
                width: parent.width           // important for horizontal alignment inside ScrollView
                height: parent.height      // important for vertical alignment inside ScrollView
                padding: 16                 // padding inside panel
                Material.background: Material.CardBackground  // Material card style

                Material.elevation: 4           // shadow depth 
                background:                     // custom background
                    Rectangle {                 // rounded rectangle
                        anchors.fill: parent    //
                        color: "#1E1E1E"
                        radius: 8               // rounded corners
                        border.color: "#333"       // border color
                        border.width: 1        // border width
                
                    Rectangle {
                        anchors.fill: parent    //  fill entire panel
                        color: "#1E1E1E"    // slightly transparent overlay
                        opacity: 0.92       // adjust opacity for effect
                        radius: 16         // rounded corners
                        border.color: Qt.rgba(0.3, 0.3, 0.3, 0.6)       // border color
                        border.width: 1     // border width 
                    }
                }



                ColumnLayout {
                    anchors.fill: parent
                    spacing: 12                 // spacing between elements

                    // Motor status
                    RowLayout {
                        Label { text: "Motor Status:"; font.bold: true }        // bold label
                        Rectangle {                     // status indicator
                            width: 18; height: 18; radius: 9  
                            color: {
                                switch(motorController.currentMotor?.state ?? "OFF") {
                                    case "RUNNING": return "#4CAF50"
                                    case "WARNING": return "#FF9800"
                                    case "ERROR":   return "#F44336"
                                    case "IDLE":    return "#2196F3"
                                    default:        return "#757575"
                                }
                            }
                        }
                        Label {
                            text: motorController.currentMotor?.state ?? "OFF"   // dynamic status text
                            color: "#ffffff"
                        }
                    }

                    RowLayout {

                        Label { text: "Select Motor by S/N:" }           // label for motor selection          
                        ComboBox {
                            Layout.fillWidth: false                      // fill width  
                            model: motorController.availableMotors
                            currentIndex: model.indexOf(motorController.currentSerialNumber)
                            onActivated: (index) => {
                                motorController.currentSerialNumber = model[index]
                            }
                            font.pixelSize: 14
                        }
                    }

                    // Позиция назначения
                    RowLayout {
                        Label { text: "Destination position:" }
                        TextField {
                            id: targetPos
                            Layout.fillWidth: true
                            placeholderText: "Destination position"
                            validator: IntValidator{bottom: -100000; top: 100000}
                        }
                        Button {
                            text: "Move Absolute"
                            onClicked: {
                                let pos = parseInt(targetPos.text) || 0
                                motorController.moveAbsolute(pos, velocity.value, acceleration.value)
                            }
                        }
                    }

                    // Motion controls buttons
                    RowLayout {
                        spacing: 8
                        
                        Button { text: "◀ Backward";  onClicked: { console.log("Backward pressed") } }
                        Button { text: "■ STOP";      highlighted: true; Material.background: Material.Red;  onClicked: { motorController.stop(); console.log("Stop pressed");}}
                        Button { text: "Forward ▶"; onClicked: { console.log("Forward pressed") }}
                        Button { text: "Home" }
                    }

                    GridLayout {
                        columns: 2
                        Label { text: "Velocity:" }
                        SpinBox { id: velocity; from: 1; to: 5000; value: 1000; editable: true }

                        Label { text: "Acceleration:" }
                        SpinBox { id: acceleration; from: 10; to: 10000; value: 2000; editable: true }
                    }

                    Rectangle { Layout.fillWidth: true; height: 1; color: "#444" }

                    // Текущие значения
                    GridLayout {
                        columns: 2
                        Label { text: "Current position:" }
                        TextField { readOnly: true; text: motorController.currentMotor?.position ?? "—" }

                        Label { text: "Running time:" }
                        TextField { readOnly: true; text: "00:00:00" }
                    }

                    CheckBox {
                        id: timeoutEnable
                        text: "Enable timeout"
                    }

                    RowLayout {
                        enabled: timeoutEnable.checked
                        Label { text: "Timeout (s):" }
                        SpinBox { from: 1; to: 3600; value: 30; editable: true }
                    }
                }
            }

        }


        // ── Правая панель: Scale ──────────────────────────────
        Pane {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                width: scrollView.width   // ← neccesary for horizontal alignment
                height: scrollView.height // ← do not set height, if want it expand naturally
                spacing: 16
                anchors.fill: parent

                RowLayout {
                    Label { text: "Scale Status:"; font.bold: true }
                    Rectangle {
                        width: 18; height: 18; radius: 9
                        color: scale.isConnected ? "#4CAF50" : "#F44336"
                    }
                    Label { text: scale.isConnected ? "CONNECTED" : "DISCONNECTED" }
                }
                
                Label { text: "Select Port:" }
                ComboBox {
                    Layout.fillWidth: true
                    model: scale.listScales()
                    onActivated: (index) => {
                        scale.update_serial_port(model[index])
                        scale.connect()
                    }
                }
                Label { text: "Weight:" }
                TextField {
                    Layout.fillWidth: true
                    readOnly: true
                    font.pixelSize: 28
                    horizontalAlignment: Text.AlignHCenter
                    text: scale.weight.toFixed(2) + " kg"
                }

                Label { text: "Power=W/T:" }
                TextField {
                    Layout.fillWidth: true
                    readOnly: true
                    text: "Rate of Change by Weight (ROC) - Weight/Time"
                    font.pixelSize: 16
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Label { text: "Poll interval (ms):" }
                    SpinBox {
                        from: 50; to: 5000; value: 100; stepSize: 50; editable: true
                        onValueModified: scale.update_poll_interval(value / 1000)
                    }
                }
            }
        }
    }
}