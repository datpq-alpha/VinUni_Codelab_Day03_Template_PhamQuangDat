"""
Lab #3: Baseline Chatbot vs ReAct Agent
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.
"""

import json
from tools import TOOL_DEFINITIONS, TOOL_MAP, get_flight_info, get_weather_forecast

SYSTEM_PROMPT = """Bạn là một ReAct Agent thông minh hỗ trợ khách hàng Vingroup.
Bạn chỉ sử dụng các công cụ sau:
{tools}

Quy trình trả lời bắt buộc:
Thought: <Suy nghĩ bước tiếp theo>
Action: {{"name": "<tên tool>", "args": {{<tham số>}}}}
Observation: <Kết quả từ tool>
... (Lặp lại cho tới khi có đủ dữ liệu)
Final Answer: <Câu trả lời hoàn chỉnh cho khách hàng>
"""

class ChatbotBaseline:
    """Baseline LLM Chatbot (Không sử dụng ReAct Loop hay Tools)"""
    def query(self, user_input: str) -> str:
        # TODO: Trả về câu trả lời tĩnh hoặc gọi LLM 1 lượt (không dùng tool)
        return {
            "status": "success",
            "answer": (
                "Tôi chưa thể tra cứu dữ liệu chuyến bay hoặc thời tiết "
                "vì chatbot baseline không sử dụng công cụ."
            ),
            "tool_calls": []
        }

class ReActAgent:
    """ReAct Agent có sử dụng Thought-Action-Observation Loop."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace = []

    @staticmethod
    def _extract_city_codes(user_input: str) -> list:
        """Trích xuất các mã sân bay được hỗ trợ."""
        import re

        return re.findall(
            r"\b(?:HAN|SGN|DAD)\b",
            user_input.upper()
        )

    @staticmethod
    def _extract_max_price(
        user_input: str,
        default: int = 5_000_000
    ) -> int:
        """Chuyển '2 triệu', '1.5 triệu', '500k' thành số VND."""
        import re

        normalized = user_input.lower().replace(",", ".")

        match = re.search(
            r"(\d+(?:\.\d+)?)\s*(triệu|trieu|k|nghìn|nghin)",
            normalized
        )

        if not match:
            return default

        value = float(match.group(1))
        unit = match.group(2)

        if unit in ("triệu", "trieu"):
            return int(value * 1_000_000)

        return int(value * 1_000)

    @staticmethod
    def _format_flights(flights: list) -> str:
        """Chuyển dữ liệu chuyến bay thành câu trả lời."""
        if not flights:
            return "Không tìm thấy chuyến bay phù hợp với yêu cầu."

        lines = []

        for flight in flights:
            price = f'{flight["price_vnd"]:,}'.replace(",", ".")

            lines.append(
                f'- {flight["flight_number"]} – '
                f'{flight["airline"]}, '
                f'khởi hành lúc {flight["departure_time"]}, '
                f'giá {price} VND'
            )

        return "Các chuyến bay phù hợp:\n" + "\n".join(lines)

    @staticmethod
    def _format_weather(weather: dict) -> str:
        """Chuyển dữ liệu thời tiết thành câu trả lời."""
        if not isinstance(weather, dict):
            return "Không thể đọc dữ liệu thời tiết."

        if "error" in weather:
            return f'Không thể tra cứu thời tiết: {weather["error"]}.'

        return (
            f'Thời tiết tại {weather["city"]}: '
            f'{weather["temperature_c"]}°C, '
            f'{weather["condition"]}, '
            f'độ ẩm {weather["humidity_pct"]}%. '
            f'Gợi ý trang phục: {weather["recommendation"]}'
        )

    @staticmethod
    def _execute_action(action: dict):
        """Thực thi action an toàn thông qua TOOL_MAP."""
        if not isinstance(action, dict):
            return {"error": "Invalid action format"}

        tool_name = str(action.get("name", "")).strip().lower()
        arguments = action.get("args", {})

        if not isinstance(arguments, dict):
            return {"error": "Tool arguments must be a dictionary"}

        tool = TOOL_MAP.get(tool_name)

        if tool is None:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return tool(**arguments)
        except (TypeError, ValueError, OSError) as exc:
            return {"error": str(exc)}

    def _max_iterations_result(self, answer: str = None) -> dict:
        """Tạo kết quả khi agent đã dùng hết số vòng lặp."""
        return {
            "status": "max_iterations_reached",
            "answer": answer or (
                "Không thể hoàn thành trong số bước tối đa."
            ),
            "iterations": len(self.trace),
            "trace": self.trace
        }

    def run(self, user_input: str) -> dict:
        # TODO 1: Khởi tạo lại trace cho mỗi truy vấn
        self.trace = []

        normalized_input = user_input.lower()
        city_codes = self._extract_city_codes(user_input)

        wants_weather = (
            "thời tiết" in normalized_input
            or "weather" in normalized_input
        )

        wants_flight = (
            len(city_codes) >= 2
            and (
                "chuyến bay" in normalized_input
                or "máy bay" in normalized_input
                or "vé" in normalized_input
            )
        )

        actions = []

        # TODO 2 và 3: Phân tích yêu cầu, tạo danh sách action
        if wants_flight:
            actions.append({
                "name": "get_flight_info",
                "args": {
                    "origin": city_codes[0],
                    "destination": city_codes[1],
                    "max_price": self._extract_max_price(user_input)
                }
            })

        if wants_weather:
            if city_codes:
                weather_city = city_codes[-1]
            else:
                weather_city = ""

            actions.append({
                "name": "get_weather_forecast",
                "args": {
                    "city_code": weather_city
                }
            })

        # Trường hợp FAQ hoặc câu hỏi không cần tool
        if not actions:
            if self.max_iterations <= 0:
                return self._max_iterations_result()

            if "vinpearl" in normalized_input:
                answer = (
                    "Chính sách đổi trả vé máy bay Vinpearl phụ thuộc "
                    "vào điều kiện của từng loại vé. Bạn nên kiểm tra "
                    "điều kiện vé hoặc liên hệ Vinpearl để xác nhận "
                    "phí đổi, hoàn và thời hạn áp dụng."
                )
            else:
                answer = (
                    "Tôi chưa xác định được yêu cầu tra cứu chuyến bay "
                    "hoặc thời tiết. Vui lòng cung cấp mã sân bay như "
                    "HAN, SGN hoặc DAD."
                )

            self.trace.append({
                "iteration": 1,
                "thought": "Câu hỏi không cần sử dụng công cụ.",
                "action": None,
                "observation": None,
                "final_answer": answer
            })

            return {
                "status": "completed",
                "answer": answer,
                "iterations": 1,
                "trace": self.trace
            }

        observations = {}
        action_index = 0

        # TODO 2: Thought-Action-Observation loop
        while action_index < len(actions):
            if len(self.trace) >= self.max_iterations:
                return self._max_iterations_result()

            action = actions[action_index]
            tool_name = action["name"]

            if tool_name == "get_flight_info":
                thought = (
                    "Cần gọi công cụ tìm chuyến bay theo hành trình "
                    "và ngân sách của khách hàng."
                )
            else:
                thought = (
                    "Cần gọi công cụ thời tiết để đưa ra gợi ý "
                    "trang phục phù hợp."
                )

            # TODO 4: Thực thi tool
            observation = self._execute_action(action)
            observations[tool_name] = observation

            trace_item = {
                "iteration": len(self.trace) + 1,
                "thought": thought,
                "action": action,
                "observation": observation
            }

            # Truy vấn chỉ cần một tool kết thúc ngay trong iteration đó
            if len(actions) == 1:
                if tool_name == "get_flight_info":
                    answer = self._format_flights(observation)
                else:
                    answer = self._format_weather(observation)

                trace_item["final_answer"] = answer
                self.trace.append(trace_item)

                return {
                    "status": "completed",
                    "answer": answer,
                    "iterations": len(self.trace),
                    "trace": self.trace
                }

            # TODO 5: Ghi observation và tiếp tục vòng lặp
            self.trace.append(trace_item)
            action_index += 1

        flight_answer = self._format_flights(
            observations.get("get_flight_info", [])
        )

        weather_answer = self._format_weather(
            observations.get(
                "get_weather_forecast",
                {"error": "Không có dữ liệu"}
            )
        )

        final_answer = f"{flight_answer}\n\n{weather_answer}"

        # Multi-step cần thêm một iteration để tạo Final Answer
        if len(self.trace) >= self.max_iterations:
            return self._max_iterations_result(final_answer)

        self.trace.append({
            "iteration": len(self.trace) + 1,
            "thought": (
                "Đã có đủ dữ liệu chuyến bay và thời tiết "
                "để tổng hợp câu trả lời."
            ),
            "action": None,
            "observation": None,
            "final_answer": final_answer
        })

        return {
            "status": "completed",
            "answer": final_answer,
            "iterations": len(self.trace),
            "trace": self.trace
        }

def main():
    user_query = "Tìm cho tôi chuyến bay từ HAN đi SGN dưới 2 triệu, rồi cho biết thời tiết SGN nên mặc gì?"
    
    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))
    
    print("\n=== RUNNING REACT AGENT ===")
    agent = ReActAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result)
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()