import pytest
import re
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_journey1_cpp_chat(page: Page):
    """Journey 1: Happy Path - Chat with C++ code generation."""
    page.goto("http://localhost:3000")
    
    # Send C++ query
    input_selector = "input[placeholder='Ask anything...']"
    page.wait_for_selector(input_selector, timeout=30000)
    page.fill(input_selector, "Write C++ code to sum an array of integers")
    page.click("button:has-text('Send'), [class*='inputBox'] button")
    
    # Verify response bubble appears and has content
    message_selector = "[data-testid='message-bubble']"
    page.wait_for_selector(message_selector, timeout=20000)
    expect(page.locator(message_selector).first).not_to_be_empty()

@pytest.mark.e2e
def test_journey2_sql_preview(page: Page):
    """Journey 2: Hybrid Brain - SQL tool triggering and structured preview."""
    page.goto("http://localhost:3000")
    
    # Send DuckDB-triggering query
    input_selector = "input[placeholder='Ask anything...']"
    page.wait_for_selector(input_selector, timeout=30000)
    page.fill(input_selector, "Show me travel spend for Q3")
    page.click("button:has-text('Send'), [class*='inputBox'] button")
    
    # Verify SQL Preview restoration
    sql_preview_selector = "[data-testid='sql-preview']"
    page.wait_for_selector(sql_preview_selector, timeout=20000)
    expect(page.locator(sql_preview_selector)).to_be_visible()
    
    # Verify SQL code visibility
    expect(page.locator("[data-testid='sql-code']")).to_contain_text("SELECT", ignore_case=True)

@pytest.mark.e2e
def test_journey3_admin_observability(page: Page):
    """Journey 3: Pipeline Observability - Admin dashboard failure tracking."""
    # Note: We rely on the /admin route existing
    page.goto("http://localhost:3000/admin")
    
    # Wait for dashboard components
    input_selector = "#ingestion-path-input"
    page.wait_for_selector(input_selector, timeout=30000)
    
    # Enqueue a corrupt/invalid path that exists on the server (seeded in E2E setup)
    bad_path = "/tests/assets/corrupt_stress.pdf"
    page.fill(input_selector, bad_path)
    page.click("button:has-text('Ingest File')")
    
    # Verify failure badge in the table
    # We look for the filename and the 'failed' status
    expect(page.get_by_text("corrupt_stress.pdf").first).to_be_visible(timeout=30000)
    expect(page.get_by_text("failed").first).to_be_visible(timeout=30000)
    
    # Verify observability details (Journey 3 extension)
    # Clicking the expansion button in the row
    page.get_by_test_id("expand-row-button").first.click()
    expect(page.get_by_test_id("job-error-details")).to_be_visible(timeout=10000)
    expect(page.get_by_text(re.compile("Traceback", re.IGNORECASE)).first).to_be_visible(timeout=10000)
    expect(page.get_by_text(re.compile("Job Details", re.IGNORECASE)).first).to_be_visible(timeout=10000)
