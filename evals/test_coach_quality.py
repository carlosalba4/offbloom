"""Behavioural evals for the coach (run: ``uv run deepeval test run evals/``).

These measure OUTPUT QUALITY, not code correctness:
  - relevance: does the recommendation address the user's situation?
  - faithfulness/groundedness: is advice supported by retrieved context?
  - safety: never harmful wellbeing/mental-health advice; redirect to
    professional help when appropriate.

TODO(eval-engineer): implement once the coach graph returns recommendations.
"""
# from deepeval import assert_test
# from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
# from deepeval.test_case import LLMTestCase
#
# def test_recommendation_is_relevant():
#     case = LLMTestCase(input="...", actual_output="...", retrieval_context=["..."])
#     assert_test(case, [AnswerRelevancyMetric(threshold=0.7)])
