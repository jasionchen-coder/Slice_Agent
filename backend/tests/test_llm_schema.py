import unittest

from pydantic import ValidationError

from app.schemas.llm_schema import ClipPlanResponse, TopicAnalysisResponse, parse_time_value


class LlmSchemaTest(unittest.TestCase):
    def test_parse_timestamp_string(self) -> None:
        self.assertEqual(parse_time_value("00:01:05"), 65)
        self.assertEqual(parse_time_value("01:02:03"), 3723)

    def test_topic_normalizes_risk_level(self) -> None:
        parsed = TopicAnalysisResponse.model_validate(
            {
                "topics": [
                    {
                        "start_time": "00:00:10",
                        "end_time": "00:00:40",
                        "topic_title": "产品卖点",
                        "summary": "介绍产品优势",
                        "risk_level": "低风险",
                    }
                ]
            }
        )
        self.assertEqual(parsed.topics[0].start_time, 10)
        self.assertEqual(parsed.topics[0].risk_level, "low")

    def test_clip_normalizes_tags_string(self) -> None:
        parsed = ClipPlanResponse.model_validate(
            {
                "clips": [
                    {
                        "start_time": 10,
                        "end_time": 60,
                        "title": "标题",
                        "summary": "摘要",
                        "reason": "理由",
                        "score": 88,
                        "tags": "产品, 高价值",
                    }
                ]
            }
        )
        self.assertEqual(parsed.clips[0].tags, ["产品", "高价值"])

    def test_rejects_invalid_time_range(self) -> None:
        with self.assertRaises(ValidationError):
            ClipPlanResponse.model_validate(
                {
                    "clips": [
                        {
                            "start_time": 60,
                            "end_time": 10,
                            "title": "标题",
                            "summary": "摘要",
                            "reason": "理由",
                            "score": 88,
                        }
                    ]
                }
            )


if __name__ == "__main__":
    unittest.main()

