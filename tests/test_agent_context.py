import fixtures.prompts as test_prompts
from fixtures.prompts import normalize_prompts

from echos_lab.engines.agent_context import AgentContext


class TestAgentContext:
    def test_is_empty(self):
        """
        Tests the is_empty function
        """
        assert not AgentContext("a", "b", "c").is_empty()
        assert not AgentContext("a", None, None).is_empty()
        assert not AgentContext(None, "b", None).is_empty()
        assert AgentContext(None, None, None).is_empty()

    def test_prompt_summary_all(self):
        """
        Tests building the prompt summary when each context is populated
        """
        context = AgentContext(
            people_context="PersonA is good",
            project_context="ProjectB is good",
            other_context="TokenC is good",
        )
        expected_summary = test_prompts.AGENT_CONTEXT_ALL
        actual_summary = context.to_prompt_summary("author")

        assert normalize_prompts(expected_summary) == normalize_prompts(actual_summary)

    def test_prompt_summary_people_only(self):
        """
        Tests building the prompt summary when only people context is populated
        """
        context = AgentContext(
            people_context="PersonA is good",
            project_context=None,
            other_context=None,
        )
        expected_summary = test_prompts.AGENT_CONTEXT_PEOPLE_ONLY
        actual_summary = context.to_prompt_summary("author")

        assert normalize_prompts(expected_summary) == normalize_prompts(actual_summary)

    def test_prompt_summary_other_only(self):
        """
        Tests building the prompt summary when only other context is populated
        """
        context = AgentContext(
            people_context=None,
            project_context=None,
            other_context="TokenC is good",
        )
        expected_summary = test_prompts.AGENT_CONTEXT_OTHER_ONLY
        actual_summary = context.to_prompt_summary("author")

        assert normalize_prompts(expected_summary) == normalize_prompts(actual_summary)

    def test_prompt_summary_people_and_other(self):
        """
        Tests building the prompt summary when only people and other context is populated
        """
        context = AgentContext(
            people_context="PersonA is good",
            project_context=None,
            other_context="TokenC is good",
        )
        expected_summary = test_prompts.AGENT_CONTEXT_PEOPLE_AND_OTHER_ONLY
        actual_summary = context.to_prompt_summary("author")

        assert normalize_prompts(expected_summary) == normalize_prompts(actual_summary)
