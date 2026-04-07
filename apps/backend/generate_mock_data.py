import os
import pandas as pd
import click
from pathlib import Path


@click.command()
def generate_data():
    """Generates dummy structured data for DuckDB to query in Phase 2."""

    # Target directory is the root-level 'data' directory
    root_dir = Path(__file__).parent.parent
    data_dir = root_dir / "data"
    data_dir.mkdir(exist_ok=True)

    # 1. Travel Spend dataset
    travel_data = [
        {
            "employee_id": "E100",
            "department": "Sales",
            "amount": 1200.50,
            "quarter": "Q1",
            "compliant": True,
        },
        {
            "employee_id": "E101",
            "department": "Engineering",
            "amount": 450.00,
            "quarter": "Q1",
            "compliant": True,
        },
        {
            "employee_id": "E100",
            "department": "Sales",
            "amount": 3400.00,
            "quarter": "Q2",
            "compliant": False,
        },
        {
            "employee_id": "E102",
            "department": "HR",
            "amount": 300.00,
            "quarter": "Q2",
            "compliant": True,
        },
        {
            "employee_id": "E103",
            "department": "Marketing",
            "amount": 800.00,
            "quarter": "Q3",
            "compliant": True,
        },
        {
            "employee_id": "E101",
            "department": "Engineering",
            "amount": 2500.00,
            "quarter": "Q3",
            "compliant": False,
        },  # Example violating policy
    ]
    df_travel = pd.DataFrame(travel_data)
    travel_path = os.path.join(data_dir, "travel_spend.parquet")
    df_travel.to_parquet(travel_path, index=False)

    click.echo(f"✅ Successfully wrote {len(travel_data)} rows to {travel_path}")

    # Print out a mock JWT token so the developer can insert it in their frontend / local testing!
    import jwt

    mock_token = jwt.encode(
        {"user_id": 1, "sub": "test_user"}, "dev_secret", algorithm="HS256"
    )

    click.echo("\n--- [Development JWT] ---")
    click.echo(
        "To interact with the secured backend quickly, use the following JWT Token:"
    )
    click.echo(mock_token)
    click.echo("-------------------------")


if __name__ == "__main__":
    generate_data()
