from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env

goldsky_api = "https://api.goldsky.com/api"
echos_subgraph = "public/project_cm2w6uknu6y1w01vw7ec0et97/subgraphs/memetokens-mainnet/2.0.0/gn"
GOLDKSY_GRAPHQL_ENDPOINT = get_env(envs.GOLDKSY_GRAPHQL_ENDPOINT, f"{goldsky_api}/{echos_subgraph}")

transport = RequestsHTTPTransport(url=GOLDKSY_GRAPHQL_ENDPOINT, use_json=True)
client = Client(transport=transport, fetch_schema_from_transport=True)

BALANCE_QUERY = gql(
    """
    query BalanceQuery($address: Bytes!) {
        accountTokenBalances(
            where: {account: $address}
        ) {
            balance
            token {
                id
                name
                symbol
                marketData {
                    graduated
                    marketCap
                    currentPrice
                    volume
                }
            }
        }
    }
"""
)


METADATA_QUERY = gql(
    """
    query GraduatedQuery($id: ID!) {
        memeToken(id: $id) {
            marketData {
                currentPrice
                graduated
            }
        }
    }
"""
)
