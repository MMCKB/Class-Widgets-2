import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: root
    title: qsTr("场景模式")

    property var sceneData: []
    property var selectedScene: null
    property string selectedSceneId: ""

    function sceneIndex(sceneId) {
        for (let index = 0; index < sceneData.length; index++) {
            if (sceneData[index].id === sceneId)
                return index
        }
        return -1
    }

    function refreshScenes() {
        sceneData = AppCentral.sceneModes.scenes
        if (selectedSceneId === "" && sceneData.length > 0)
            selectedSceneId = AppCentral.sceneModes.activeSceneId || sceneData[0].id

        selectedScene = null
        for (let index = 0; index < sceneData.length; index++) {
            if (sceneData[index].id === selectedSceneId) {
                selectedScene = sceneData[index]
                break
            }
        }
        if (selectedScene === null && sceneData.length > 0) {
            selectedSceneId = sceneData[0].id
            selectedScene = sceneData[0]
        }
    }

    Component.onCompleted: refreshScenes()

    Connections {
        target: AppCentral.sceneModes
        function onChanged() { root.refreshScenes() }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8

        Text {
            typography: Typography.BodyStrong
            text: qsTr("场景模式")
        }

        Text {
            Layout.fillWidth: true
            color: Colors.proxy.textSecondaryColor
            wrapMode: Text.Wrap
            text: qsTr("将当前的界面外观、小组件位置与交互偏好保存为场景。考试模式也是可改名、可删除的场景预设；应用它会先显示进入提示，再打开沉浸式时钟。")
        }

        SettingCard {
            Layout.fillWidth: true
            icon.name: "ic_fluent_add_circle_20_regular"
            title: qsTr("保存当前设置")
            description: qsTr("创建场景时会保存当前主题、缩放、透明度、圆角、位置、图层、迷你模式和悬停淡出设置。")

            RowLayout {
                spacing: 8

                TextField {
                    id: newSceneName
                    Layout.fillWidth: true
                    placeholderText: qsTr("例如：上课展示、午休、演示")
                    onAccepted: createSceneButton.clicked()
                }

                Button {
                    id: createSceneButton
                    text: qsTr("创建场景")
                    enabled: newSceneName.text.trim().length > 0
                    onClicked: {
                        if (AppCentral.sceneModes.createScene(newSceneName.text)) {
                            newSceneName.clear()
                            root.refreshScenes()
                        }
                    }
                }
            }
        }

        SettingCard {
            Layout.fillWidth: true
            icon.name: "ic_fluent_window_multiple_20_regular"
            title: qsTr("已保存的场景")
            description: qsTr("场景仅保存在本机；你可以随时应用、更新或删除。")

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    ComboBox {
                        id: sceneSelector
                        Layout.fillWidth: true
                        textRole: "name"
                        model: root.sceneData
                        currentIndex: root.sceneIndex(root.selectedSceneId)
                        onActivated: {
                            if (currentIndex >= 0 && currentIndex < root.sceneData.length) {
                                root.selectedSceneId = root.sceneData[currentIndex].id
                                root.refreshScenes()
                            }
                        }
                    }

                    Button {
                        text: qsTr("删除")
                        enabled: root.selectedScene !== null
                        onClicked: {
                            if (AppCentral.sceneModes.deleteScene(root.selectedSceneId)) {
                                root.selectedSceneId = ""
                                root.refreshScenes()
                            }
                        }
                    }
                }

                Text {
                    visible: root.sceneData.length === 0
                    color: Colors.proxy.textSecondaryColor
                    text: qsTr("尚未创建场景。请先保存当前设置。")
                }
            }
        }

        SettingCard {
            Layout.fillWidth: true
            visible: root.selectedScene !== null
            icon.name: "ic_fluent_window_ad_20_regular"
            title: root.selectedScene ? root.selectedScene.name : qsTr("场景")
            description: root.selectedScene && root.selectedScene.kind === "exam"
                         ? qsTr("应用后会先提示正在进入考试模式，再打开全屏沉浸式时钟。该场景可以改名或删除。")
                         : (root.selectedScene && root.selectedScene.id === AppCentral.sceneModes.activeSceneId
                            ? qsTr("当前已应用此场景。")
                            : qsTr("选择应用后会立即切换到此场景保存的设置。"))

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                TextField {
                    id: sceneNameField
                    Layout.fillWidth: true
                    placeholderText: qsTr("场景名称")
                    text: root.selectedScene ? root.selectedScene.name : ""
                    onEditingFinished: {
                        if (root.selectedScene !== null)
                            AppCentral.sceneModes.renameScene(root.selectedSceneId, text)
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Button {
                        Layout.fillWidth: true
                        text: root.selectedScene && root.selectedScene.kind === "exam"
                              ? qsTr("进入考试模式")
                              : qsTr("应用此场景")
                        onClicked: AppCentral.sceneModes.applyScene(root.selectedSceneId)
                    }

                    Button {
                        Layout.fillWidth: true
                        visible: !root.selectedScene || root.selectedScene.kind !== "exam"
                        text: qsTr("用当前设置更新")
                        onClicked: AppCentral.sceneModes.updateSceneFromCurrent(root.selectedSceneId)
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            visible: AppCentral.sceneModes.statusText.length > 0
            text: AppCentral.sceneModes.statusText
            color: Colors.proxy.textSecondaryColor
            wrapMode: Text.Wrap
        }
    }
}
