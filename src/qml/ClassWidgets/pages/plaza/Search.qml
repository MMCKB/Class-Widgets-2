import QtQuick
import QtQuick.Layouts
import RinUI
import ClassWidgets.Components

FluentPage {
    id: root
    title: qsTr("Search")
    horizontalPadding: 0
    wrapperWidth: width - 42 * 2

    // 由导航 push 传入的搜索关键词
    property string query: ""
    // 页内搜索框当前输入（提交后才更新 query）
    readonly property string baseUrl: PlazaBridge.baseUrl
    property var plugins: []
    property var tags: []
    property var suggestions: []
    property var recommendedPlugins: []
    property string activeTag: ""
    property string sort: "relevance"
    property int page: 1
    property int perPage: 12
    property int total: 0
    property int totalPages: 1
    property bool loading: false
    property bool suggestionsLoading: false
    property bool recommendedPluginsLoading: false
    property string errorMessage: ""
    property int searchSerial: 0
    property int suggestionsSerial: 0
    property int recommendationsSerial: 0
    property var activeSearchRequest: null
    property var activeTagsRequest: null
    property var activeSuggestionsRequest: null
    property var activeRecommendationsRequest: null

    readonly property bool hasQuery: query.trim().length > 0

    onQueryChanged: {
        activeTag = ""
        if (hasQuery)
            search(1)
        else {
            loadSuggestions()
            loadRecommendedPlugins()
        }
    }

    function request(url, callback, failure) {
        var xhr = new XMLHttpRequest()
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            if (xhr.status >= 200 && xhr.status < 300) {
                try { callback(JSON.parse(xhr.responseText)) }
                catch (error) { failure(qsTr("Invalid server response.")) }
            } else {
                failure(xhr.status + " " + xhr.statusText)
            }
        }
        xhr.open("GET", url)
        xhr.send()
        return xhr
    }

    function search(nextPage) {
        var serial = ++searchSerial
        if (activeSearchRequest)
            activeSearchRequest.abort()
        if (!hasQuery) {
            plugins = []
            total = 0
            totalPages = 1
            return
        }
        page = nextPage || 1
        loading = true
        errorMessage = ""
        var params = "?q=" + encodeURIComponent(query.trim())
            + "&page=" + page + "&per_page=" + perPage
            + "&sort=" + encodeURIComponent(sort)
        if (activeTag) params += "&tag=" + encodeURIComponent(activeTag)
        activeSearchRequest = request(baseUrl + "/api/plugins/search" + params, function(response) {
            if (serial !== searchSerial)
                return
            if (response.ok === false) {
                plugins = []
                total = 0
                totalPages = 1
                errorMessage = response.error || qsTr("The plaza rejected the request.")
            } else {
                plugins = response.data instanceof Array ? response.data : []
                total = response.meta && response.meta.total !== undefined ? response.meta.total : plugins.length
                totalPages = response.meta && response.meta.total_pages ? response.meta.total_pages : 1
            }
            loading = false
        }, function(error) {
            if (serial !== searchSerial)
                return
            plugins = []
            total = 0
            totalPages = 1
            errorMessage = qsTr("Unable to search plugins: ") + error
            loading = false
        })
    }

    function loadTags() {
        if (activeTagsRequest)
            activeTagsRequest.abort()
        activeTagsRequest = request(baseUrl + "/api/plugins/tags", function(response) {
            tags = response.data instanceof Array ? response.data : []
        }, function() { tags = [] })
    }

    function loadSuggestions() {
        var serial = ++suggestionsSerial
        if (activeSuggestionsRequest)
            activeSuggestionsRequest.abort()
        suggestions = []
        suggestionsLoading = true
        activeSuggestionsRequest = request(baseUrl + "/api/plugins/suggest?limit=12", function(response) {
            if (serial !== suggestionsSerial)
                return
            suggestions = response.ok !== false && response.data instanceof Array ? response.data : []
            suggestionsLoading = false
        }, function() {
            if (serial !== suggestionsSerial)
                return
            suggestions = []
            suggestionsLoading = false
        })
    }

    function loadRecommendedPlugins() {
        var serial = ++recommendationsSerial
        if (activeRecommendationsRequest)
            activeRecommendationsRequest.abort()
        recommendedPlugins = []
        recommendedPluginsLoading = true
        activeRecommendationsRequest = request(baseUrl + "/api/plugins/random?limit=6", function(response) {
            if (serial !== recommendationsSerial)
                return
            recommendedPlugins = response.ok !== false && response.data instanceof Array ? response.data : []
            recommendedPluginsLoading = false
        }, function() {
            if (serial !== recommendationsSerial)
                return
            recommendedPlugins = []
            recommendedPluginsLoading = false
        })
    }

    function chooseSuggestion(item) {
        if (!item)
            return
        if (item.type === "plugin" && item.pluginId) {
            navigationView.push(PathManager.qml("pages/plaza/Plugin.qml"), { pluginId: item.pluginId })
        } else if (item.value) {
            query = item.value
        }
    }

    function selectTag(tagId) {
        activeTag = tagId
        search(1)
    }

    function selectSort(value) {
        sort = value
        search(1)
    }

    Component.onCompleted: {
        loadTags()
        if (hasQuery)
            search(1)
        else {
            loadSuggestions()
            loadRecommendedPlugins()
        }
    }

    Component.onDestruction: {
        ++searchSerial
        ++suggestionsSerial
        ++recommendationsSerial
        if (activeSearchRequest)
            activeSearchRequest.abort()
        if (activeSuggestionsRequest)
            activeSuggestionsRequest.abort()
        if (activeRecommendationsRequest)
            activeRecommendationsRequest.abort()
        if (activeTagsRequest)
            activeTagsRequest.abort()
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 16

        Grid {
            Layout.fillWidth: true
            columns: Math.floor(width / (300 + 6))
            rowSpacing: 12
            columnSpacing: 12
            layoutDirection: GridLayout.LeftToRight
            visible: !root.hasQuery && !root.suggestionsLoading && root.suggestions.length > 0

            Repeater {
                model: root.suggestions

                delegate: Button {
                    width: 300
                    required property var modelData
                    flat: true
                    highlighted: true
                    contentItem: RowLayout {
                        anchors.fill: parent
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.margins: 12
                        spacing: 6

                        Icon {
                            name: "ic_fluent_search_20_regular"
                            color: Colors.proxy.primaryColor
                            Layout.alignment: Qt.AlignLeft | Qt.AlignVCenter
                        }

                        Text {
                            text: modelData.label || modelData.value || ""
                            color: Colors.proxy.primaryColor
                            Layout.alignment: Qt.AlignLeft | Qt.AlignVCenter
                        }

                        Item { Layout.fillWidth: true }
                    }
                    // icon.name: "ic_fluent_search_20_regular"
                    // text: modelData.label || modelData.value || ""
                    onClicked: root.chooseSuggestion(modelData)
                }
            }
        }

        PlazaLoading {
            Layout.fillWidth: true
            visible: !root.hasQuery && (root.suggestionsLoading || root.recommendedPluginsLoading)
        }

        Text {
            Layout.fillWidth: true
            Layout.topMargin: 12
            visible: !root.hasQuery && !root.recommendedPluginsLoading && root.recommendedPlugins.length > 0
            text: qsTr("Suggested plugins")
            typography: Typography.BodyLarge
        }

        PluginGrid {
            Layout.fillWidth: true
            visible: !root.hasQuery && !root.recommendedPluginsLoading && root.recommendedPlugins.length > 0
            plugins: root.recommendedPlugins
            loading: false
        }

        // 头部：标题（左）+ 排序（右），下方标签筛选
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 12
            visible: root.hasQuery

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Text {
                    Layout.fillWidth: true
                    text: "\u201C" + root.query + "\u201D"
                    typography: Typography.Title
                    elide: Text.ElideRight
                }

                DropDownButton {
                    Layout.alignment: Qt.AlignRight
                    enabled: !root.loading
                    text: root.sort === "relevance" ? qsTr("Relevance")
                        : root.sort === "name" ? qsTr("Name")
                        : root.sort === "rating" ? qsTr("Rating")
                        : root.sort === "downloads" ? qsTr("Downloads")
                        : qsTr("Latest")
                    icon.name: "ic_fluent_arrow_sort_20_regular"

                    MenuItem { text: qsTr("Relevance"); onTriggered: root.selectSort("relevance") }
                    MenuItem { text: qsTr("Latest"); onTriggered: root.selectSort("latest") }
                    MenuItem { text: qsTr("Name"); onTriggered: root.selectSort("name") }
                    MenuItem { text: qsTr("Rating"); onTriggered: root.selectSort("rating") }
                    MenuItem { text: qsTr("Downloads"); onTriggered: root.selectSort("downloads") }
                }
            }

            Segmented {
                enabled: !root.loading

                SegmentedItem {
                    text: qsTr("All")
                    checked: root.activeTag === ""
                    onClicked: root.selectTag("")
                }

                Repeater {
                    model: root.tags instanceof Array ? root.tags.slice(0, 5) : []

                    delegate: SegmentedItem {
                        required property var modelData
                        readonly property string tagId: modelData.id || modelData.name || ""
                        text: modelData.name || modelData.id || ""
                        checked: root.activeTag === tagId
                        onClicked: root.selectTag(tagId)
                    }
                }
            }
        }

        PlazaLoading {
            Layout.fillWidth: true
            visible: root.hasQuery && root.loading
        }

        PluginGrid {
            Layout.fillWidth: true
            visible: root.hasQuery && !root.loading && root.errorMessage.length === 0 && root.plugins.length > 0
            plugins: root.plugins
            loading: false
        }

        ErrorState {
            Layout.fillWidth: true
            visible: root.hasQuery && !root.loading && root.errorMessage.length > 0
            title: qsTr("Could not search plugins")
            description: root.errorMessage
            onRetryRequested: root.search(root.page)
        }

        EmptyState {
            Layout.fillWidth: true
            visible: !root.hasQuery
                && !root.suggestionsLoading
                && !root.recommendedPluginsLoading
                && root.suggestions.length === 0
                && root.recommendedPlugins.length === 0
            // iconName: "ic_fluent_search_24_regular"
            title: qsTr("Search the plaza")
            description: qsTr("No suggested keywords are available.")
        }

        EmptyState {
            Layout.fillWidth: true
            visible: root.hasQuery && !root.loading && root.errorMessage.length === 0 && root.plugins.length === 0
            // iconName: "ic_fluent_search_info_24_regular"
            title: qsTr("No plugins found")
            description: qsTr("Try another search or category.")
        }

        Pagination {
            Layout.alignment: Qt.AlignHCenter
            visible: root.hasQuery && !root.loading && root.errorMessage.length === 0 && root.totalPages > 1
            currentPage: root.page
            totalPages: root.totalPages
            onPageRequested: function(value) { root.search(value) }
        }
    }
}
