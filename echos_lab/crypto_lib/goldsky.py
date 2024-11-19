from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import os

GRAPHQL_ENDPOINT = os.getenv("GRAPHQL_ENDPOINT", "")
if GRAPHQL_ENDPOINT == "":
    raise ValueError("GRAPHQL_ENDPOINT not found in .env file")

transport = RequestsHTTPTransport(url=GRAPHQL_ENDPOINT, use_json=True)
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
