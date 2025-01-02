import json
from dataclasses import dataclass

import gspread  # type: ignore
from google.oauth2 import service_account  # type: ignore
from gspread import Client, Spreadsheet, WorksheetNotFound  # type: ignore
from gspread.http_client import BackOffHTTPClient  # type: ignore

from echos_lab.common import utils
from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env, get_env_or_raise
from echos_lab.engines.personalities.profiles import AgentProfile

GSHEET_SCOPE: tuple[str] = ("https://www.googleapis.com/auth/spreadsheets",)

# Module level sheets singleton storage
_sheets_client: Client | None = None


@dataclass
class WorksheetConfig:
    """
    The required worksheet and column names for the agent context gsheets file
    """

    PEOPLE_WORKSHEET_NAME: str = "people"
    PROJECTS_WORKSHEET_NAME: str = "projects"
    OTHER_WORKSHEET_NAME: str = "other"
    MEME_WORKSHEET_NAME: str = "meme"
    AUTHOR_WORKSHEET_NAME: str = "author"
    CONTEXT_COLUMN_NAME: str = "context"


@dataclass
class AgentContext:
    people_context: str | None = None
    project_context: str | None = None
    other_context: str | None = None
    meme_context: str | None = None
    author_context: dict | None = None

    def has_author_context(self, author: str) -> bool:
        """
        Checks if both the author context dict is non-empty and the specified author is in the dict
        """
        return self.author_context is not None and author in self.author_context

    def to_prompt_summary(self, author: str) -> str:
        """
        Builds a summary of the context with XML tags that can be passed into the LLM prompt
        """
        if self.is_empty():
            return ""

        people_summary = utils.wrap_xml_tag(tag="people_context", info=self.people_context)
        project_summary = utils.wrap_xml_tag(tag="project_context", info=self.project_context)
        other_summary = utils.wrap_xml_tag(tag="other_context", info=self.other_context)
        meme_summary = utils.wrap_xml_tag(tag="meme_context", info=self.meme_context)
        author_summary = self.get_author_summary(author)

        full_context = f"{author_summary}{people_summary}{project_summary}{other_summary}{meme_summary}"

        return utils.wrap_xml_tag(tag="crypto_context", info=full_context)

    def get_author_summary(self, author: str) -> str:
        """
        The author summary is the most important section in crypto context so we place a special emphasis on it
        """
        author_context = self.author_context[author] if self.has_author_context(author) else None  # type: ignore
        author_info_header = (
            "Next, review your intel about the author of the tweet you're responding to. This is IMPORTANT."
            + " This is the most critical piece of information when crafting replies."
            + " Draw context and details from this ALWAYS,"
            + " it leads to very high engagement and your fans love it!"
        )
        author_info = (
            f"{author_info_header}\nIntel From the author (in the format of an analysis"
            + f" of their profile and persona):\n@{author}:{author_context}"
            if author_context
            else "We have no author intel about the author of this tweet."
        )
        author_summary = utils.wrap_xml_tag(tag="tweet_author_intel", info=author_info)
        return author_summary

    def is_empty(self) -> bool:
        return (
            self.people_context is None
            and self.project_context is None
            and self.other_context is None
            and self.meme_context is None
            and self.author_context is None
        )


def get_gsheets_client() -> Client:  # type: ignore
    """
    Gets or creates a google sheet client
    """
    global _sheets_client

    if not _sheets_client:
        auth_dict_contents = get_env_or_raise(envs.GOOGLE_SHEETS_AUTH)
        auth_dict = json.loads(auth_dict_contents, strict=False)

        creds = service_account.Credentials.from_service_account_info(auth_dict, scopes=GSHEET_SCOPE)
        _sheets_client = gspread.authorize(creds, http_client=BackOffHTTPClient)  # type: ignore

    return _sheets_client


def build_context_string_from_column(spreadsheet: Spreadsheet, worksheet_name: str) -> str | None:
    """
    Helper function to build up a context string that can be passed into the agent prompt

    This assumes the worksheet has a "context" column

    Args:
        spreadsheet: The global or local spreadsheet consisting of different context tabs (aka "worksheets")
        worksheet: The name of the worksheet (aka tab)

    Returns:
       A string with new line deliminated pieces of context, or None if the worksheet does not exist
    """
    # Load the worksheet (tab) from the spreadsheet (document)
    # If it doesn't exist, return None
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except WorksheetNotFound:
        return None

    # Collect the sheet info into a list of dicts, where the keys of the dicts are the columnn
    # e.g. [{'columnA': '...', 'columnA': '...', 'context': '...'}, ...]
    raw_sheet_data = worksheet.get_all_records()

    # Extract out the rows for the context column
    context = [str(record[WorksheetConfig.CONTEXT_COLUMN_NAME]) for record in raw_sheet_data]

    # Remove all empty rows
    context = [row for row in context if row.strip() != ""]

    # Turn into a string
    context_str = "\n".join([row for row in context if row.strip() != ""])

    return context_str


def build_author_contexts_from_column(spreadsheet: Spreadsheet, worksheet_name: str) -> dict | None:
    """
    Helper function to build up a context dict that can be passed into the agent prompt

    This assumes the worksheet has a "context" column where each row is in the format:
    "username: context information"

    Args:
        spreadsheet: The global or local spreadsheet consisting of different context tabs (aka "worksheets")
        worksheet: The name of the worksheet (aka tab)

    Returns:
       A dictionary mapping usernames to their context information, or None if the worksheet does not exist
    """
    # Load the worksheet (tab) from the spreadsheet (document)
    # If it doesn't exist, return None
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except WorksheetNotFound:
        return None

    # Collect the sheet info into a list of dicts, where the keys of the dicts are the columnn
    # e.g. [{'columnA': '...', 'columnA': '...', 'context': '...'}, ...]
    raw_sheet_data = worksheet.get_all_records()

    # Create a dictionary mapping usernames to their context
    context_dict = {}
    for record in raw_sheet_data:
        context_text = str(record[WorksheetConfig.CONTEXT_COLUMN_NAME]).strip()
        if context_text:
            # Split on first colon to separate username and context
            parts = context_text.split(':', 1)
            if len(parts) == 2:
                username = parts[0].strip()
                context = parts[1].strip()
                context_dict[username] = context

    return context_dict


def _read_agent_context_worksheet(client: Client, spreadsheet_id: str) -> AgentContext:
    """
    Reads either the local or global agent context from the specified worksheet

    It will try to read the following tabs:
     - people
     - projects
     - other
     - meme
     - author

    If any of the tabs don't exist, the relevant field in the AgentContext will be None

    Args:
        client: The googlesheets client
        spreadsheet_id: The ID of the spreadsheet - can be either from global or local context
    """
    # Load the spreadsheet (document), and worksheets (individual tabs in spreadsheet)
    spreadsheet = client.open_by_key(spreadsheet_id)

    # Build the context string for each (they can be None if any of the worksheet names don't exist)
    people_context = build_context_string_from_column(spreadsheet, WorksheetConfig.PEOPLE_WORKSHEET_NAME)
    project_context = build_context_string_from_column(spreadsheet, WorksheetConfig.PROJECTS_WORKSHEET_NAME)
    other_context = build_context_string_from_column(spreadsheet, WorksheetConfig.OTHER_WORKSHEET_NAME)
    meme_context = build_context_string_from_column(spreadsheet, WorksheetConfig.MEME_WORKSHEET_NAME)
    author_context = build_author_contexts_from_column(spreadsheet, WorksheetConfig.AUTHOR_WORKSHEET_NAME)

    return AgentContext(
        people_context=people_context,
        project_context=project_context,
        other_context=other_context,
        meme_context=meme_context,
        author_context=author_context,
    )


def read_agent_context_worksheets() -> tuple[AgentContext | None, AgentContext | None]:
    """
    Reads the agent context from a google sheet

    Must provide the following environment variables:
     - GOOGLE_SHEETS_AUTH: The json auth contents of the service account
     - AGENT_CONTEXT_GLOBAL_SPREADSHEET_ID: The spreadsheet ID with the global agent context
     - AGENT_CONTEXT_LOCAL_SPREADSHEET_ID: The spreadsheet ID with the local agent context

    Returns:
        A tuple with global and local agent contexts, each optionally None if they aren't configured
    """
    # Determine if gsheets is configured by checking the environment variables
    local_sheet_id = get_env(envs.AGENT_CONTEXT_LOCAL_SPREADSHEET_ID)
    global_sheet_id = get_env(envs.AGENT_CONTEXT_GLOBAL_SPREADSHEET_ID)

    # If it's not configured, return None
    if not local_sheet_id and not global_sheet_id:
        return None, None

    # Get the gsheets client
    client = get_gsheets_client()

    # Load the global context (if it's configured)
    global_context: AgentContext | None = None
    if global_sheet_id:
        global_context = _read_agent_context_worksheet(client=client, spreadsheet_id=global_sheet_id)

    # Load the local context (if it's configured)
    # If both local and global were configured, concatenate them both
    local_context: AgentContext | None = None
    if local_sheet_id:
        local_context = _read_agent_context_worksheet(client=client, spreadsheet_id=local_sheet_id)

    return global_context, local_context


def get_agent_context_from_profile(profile: AgentProfile) -> tuple[AgentContext | None, AgentContext | None]:
    """
    Gets the global and local agent context for the given profile
    Global context must be sourced from gsheets
    Local context will source from gsheets if configured, otherwise, it will fall back to the agent profile
    """
    # Attempt to load the global and local contexts from google sheets
    global_context, local_context = read_agent_context_worksheets()

    # If the local context is not in google sheets, pull instead from the agent profile
    if not local_context:
        _local_context = AgentContext(
            people_context=profile.people_context,
            project_context=profile.project_context,
            other_context=profile.other_context,
        )
        local_context = _local_context if not _local_context.is_empty() else None

    return global_context, local_context
