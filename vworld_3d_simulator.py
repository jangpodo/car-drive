
import streamlit as st
import streamlit.components.v1 as components
from urllib.parse import quote

st.set_page_config(
    page_title="서울 3D 운전 교실",
    page_icon="🚗",
    layout="wide"
)

st.title("🚗 서울 3D 운전 교실")
st.subheader("브이월드 3D 지도 연결 진단")

st.info(
    "현재는 자동차 기능을 잠시 제외하고 "
    "3D 지도 자체가 정상적으로 표시되는지 확인하는 단계입니다."
)

try:
    api_key = st.secrets["VWORLD_API_KEY"]
except Exception:
    st.error("VWORLD_API_KEY를 Streamlit Secrets에서 찾을 수 없습니다.")
    st.stop()

if not str(api_key).strip():
    st.error("VWORLD_API_KEY 값이 비어 있습니다.")
    st.stop()

encoded_key = quote(str(api_key).strip(), safe="")
st.write("API 키 읽기 여부:", bool(encoded_key))
st.write("API 키 길이:", len(encoded_key))
html = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    font-family: Arial, sans-serif;
    background: #e8edf2;
}

#map {
    width: 100%;
    height: 650px;
    background: #e8edf2;
}

#status {
    padding: 10px;
    background: #172b40;
    color: white;
    font-size: 14px;
    min-height: 22px;
}

#error {
    display: none;
    padding: 12px;
    margin: 8px;
    background: #8b2424;
    color: white;
    white-space: pre-wrap;
    font-size: 13px;
}
</style>

<script
src="https://map.vworld.kr/js/webglMapInit.js.do?version=3.0&apiKey=__VWORLD_KEY__">
</script>
</head>

<body>

<div id="status">브이월드 라이브러리 확인 중...</div>
<div id="error"></div>
<div id="map"></div>

<script>
(function () {

    const status = document.getElementById("status");
    const errorBox = document.getElementById("error");

    function showError(message) {
        status.textContent = "지도 초기화 실패";
        errorBox.style.display = "block";
        errorBox.textContent = message;
        console.error("[VWorld 진단]", message);
    }

    window.addEventListener("error", function (event) {
        console.error(
            "[JavaScript 오류]",
            event.message,
            event.filename,
            event.lineno
        );
    });

    window.addEventListener("unhandledrejection", function (event) {
        console.error("[비동기 오류]", event.reason);
    });

    if (!window.vw) {
        showError(
            "브이월드 라이브러리를 불러오지 못했습니다.\n" +
            "브라우저 Console에서 스크립트 요청 오류를 확인해야 합니다."
        );
        return;
    }

    try {

        status.textContent = "3D 지도 생성 중...";

        const options = {
            mapId: "map",
            initPosition: new vw.CameraPosition(
                new vw.CoordZ(126.9780, 37.5665, 1800),
                new vw.Direction(0, -45, 0)
            ),
            logo: true,
            navigation: true
        };

        const map = new vw.Map();
        map.setOption(options);

        // 지도가 준비된 뒤 실행될 콜백을 먼저 등록
        vw.ws3dInitCallBack = function () {

            try {
                const viewer = ws3d.viewer;

                if (!viewer) {
                    showError(
                        "지도 초기화 콜백은 실행됐지만 Viewer를 찾지 못했습니다."
                    );
                    return;
                }

                status.textContent =
                    "3D 지도 초기화 완료! 서울시청 주변을 확인해 보세요.";

                console.log("[VWorld 진단] Viewer 확인 성공", viewer);

            } catch (error) {
                showError(
                    "지도 초기화 콜백 오류: " + error.message
                );
            }
        };

        map.start();

        // 초기화 완료 여부 확인
        setTimeout(function () {
            if (
                status.textContent === "3D 지도 생성 중..."
            ) {
                showError(
                    "25초 동안 지도 초기화 완료 신호를 받지 못했습니다.\n" +
                    "Console의 빨간 오류를 확인해야 합니다."
                );
            }
        }, 25000);

    } catch (error) {
        showError(
            "지도 생성 과정에서 오류 발생: " + error.message
        );
    }

})();
</script>

</body>
</html>
"""

html = html.replace("__VWORLD_KEY__", encoded_key)

components.html(
    html,
    height=680,
    scrolling=False
)
