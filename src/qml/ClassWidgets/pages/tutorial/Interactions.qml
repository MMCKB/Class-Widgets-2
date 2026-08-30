import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../../Components/tutorial" as TutorialComponents

TutorialComponents.TutorialPage {
    id: root

    property var tutorial
    title: qsTr("Choose widget interactions")
    description: qsTr("Decide how widgets get out of your way while you work.")
    currentStep: 4
    totalSteps: 6
    icon.source: PathManager.images("icons/cw2_settings.png")

    function hidePreviewSource(name) {
        return PathManager.images("tutorial/" + name + (Theme.isDark() ? "-dark.png" : "-light.png"))
    }

    ColumnLayout {
        width: parent.width
        spacing: 4

        SettingExpander {
            Layout.fillWidth: true
            Layout.minimumHeight: 200
            icon.name: "ic_fluent_slide_hide_20_regular"
            title: qsTr("Hide Behavior")
            description: qsTr("Choose whether widgets disappear or become compact")
            expanded: true

            ButtonGroup {
                id: hideModeGroup
            }

            SettingItem {
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Repeater {
                        model: [
                            {
                                "name": qsTr("Hide"),
                                "miniMode": false,
                                "preview": "hide_default"
                            },
                            {
                                "name": qsTr("Mini Mode"),
                                "miniMode": true,
                                "preview": "hide_mini"
                            }
                        ]

                        delegate: ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4

                            Image {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 72
                                source: root.hidePreviewSource(modelData.preview)
                                fillMode: Image.PreserveAspectFit
                                asynchronous: true
                            }

                            RadioButton {
                                Layout.fillWidth: true
                                text: modelData.name
                                checked: Configs.data.interactions.hide.mini_mode === modelData.miniMode
                                enabled: !Configs.isKeyLocked("interactions.hide.mini_mode")
                                ButtonGroup.group: hideModeGroup
                                onClicked: Configs.set("interactions.hide.mini_mode", modelData.miniMode)
                            }
                        }
                    }
                }
            }
        }

        SettingCard {
            Layout.fillWidth: true
            icon.name: "ic_fluent_tap_single_20_regular"
            title: qsTr("Tap to Hide")
            description: qsTr("Click on a widget to hide it, click it again to bring it back")

            Switch {
                enabled: !Configs.isKeyLocked("interactions.hide.clicked")
                onCheckedChanged: Configs.set("interactions.hide.clicked", checked)
                Component.onCompleted: checked = Configs.data.interactions.hide.clicked
            }
        }

        SettingCard {
            Layout.fillWidth: true
            icon.name: "ic_fluent_cursor_20_regular"
            title: qsTr("Hover Fade")
            description: qsTr("Hover to make widgets transparent and let clicks pass through")

            Switch {
                enabled: !Configs.isKeyLocked("interactions.hover_fade")
                onCheckedChanged: Configs.set("interactions.hover_fade", checked)
                Component.onCompleted: checked = Configs.data.interactions.hover_fade
            }
        }

        // SettingExpander {
        //     Layout.fillWidth: true
        //     icon.name: "ic_fluent_eye_off_20_regular"
        //     title: qsTr("Auto Hide")
        //     description: qsTr("Automatically hide widgets in specific situations")
        //     expanded: true
        //
        //     SettingItem {
        //         ColumnLayout {
        //             Layout.fillWidth: true
        //
        //             CheckBox {
        //                 Layout.fillWidth: true
        //                 text: qsTr("Hide when in class")
        //                 enabled: !Configs.isKeyLocked("interactions.hide.in_class")
        //                 onCheckedChanged: Configs.set("interactions.hide.in_class", checked)
        //                 Component.onCompleted: checked = Configs.data.interactions.hide.in_class
        //             }
        //
        //             CheckBox {
        //                 Layout.fillWidth: true
        //                 text: qsTr("Hide when a window is maximized")
        //                 enabled: !Configs.isKeyLocked("interactions.hide.maximized") && Qt.platform.os === "windows"
        //                 onCheckedChanged: Configs.set("interactions.hide.maximized", checked)
        //                 Component.onCompleted: checked = Configs.data.interactions.hide.maximized
        //             }
        //
        //             CheckBox {
        //                 Layout.fillWidth: true
        //                 text: qsTr("Hide when a window enters fullscreen")
        //                 enabled: !Configs.isKeyLocked("interactions.hide.fullscreen") && Qt.platform.os === "windows"
        //                 onCheckedChanged: Configs.set("interactions.hide.fullscreen", checked)
        //                 Component.onCompleted: checked = Configs.data.interactions.hide.fullscreen
        //             }
        //         }
        //     }
        // }
    }
}
