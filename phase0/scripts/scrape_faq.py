"""
scripts/scrape_faq.py

Populates data/raw_docs/{topic_key}/ with FAQ text files.
Default mode uses built-in sample FAQ content (no network needed).
Pass --url to scrape a live page instead.

Usage:
    python scripts/scrape_faq.py --topic kyc_onboarding
    python scripts/scrape_faq.py --topic all
    python scripts/scrape_faq.py --topic kyc_onboarding --output data/raw_docs --url https://example.com/faq
"""

import argparse
import os
import sys

# Allow running from repo root or from scripts/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Built-in FAQ content — one entry per topic with rich Q&A text
# ---------------------------------------------------------------------------

SAMPLE_FAQ: dict[str, str] = {
    "kyc_onboarding": """
KYC and Account Onboarding — Frequently Asked Questions

What is KYC and why is it required?
KYC stands for Know Your Customer. It is a mandatory regulatory process that financial institutions must follow to verify the identity of their clients. KYC is required by SEBI and RBI guidelines to prevent money laundering, fraud, and other financial crimes. Without completing KYC, you cannot invest in mutual funds, open a demat account, or access most financial services in India.

What documents are required for KYC?
For individual investors, the following documents are required:
Identity Proof: PAN card (mandatory), Aadhaar card, passport, voter ID, or driving licence.
Address Proof: Aadhaar card, utility bill (not older than 3 months), bank statement, or rental agreement.
Photograph: A recent passport-size photograph.
For non-individual entities such as companies or trusts, additional documents like the Certificate of Incorporation, Memorandum of Association, and board resolution may be required.

What is the difference between KYC and eKYC?
Traditional KYC involves submitting physical copies of documents at a branch or through a courier. eKYC (electronic KYC) is a paperless process that uses your Aadhaar number and biometric or OTP-based verification. eKYC is faster and can be completed online within minutes. Both are equally valid for most investment purposes.

How long does the KYC process take?
In-person KYC is typically completed within 3 to 5 business days after document submission. eKYC using Aadhaar OTP is usually completed instantly or within 24 hours. Video KYC, where a representative verifies your identity via a video call, is generally completed within 1 to 2 business days.

Can I invest without completing KYC?
No. SEBI regulations mandate that all investors complete their KYC before making any investments in mutual funds, equities, or bonds. However, you can browse fund options and learn about investments without KYC.

What is the KYC registration process with a KRA?
KYC Registration Agencies (KRAs) maintain a centralised KYC database. When you complete KYC with one SEBI-registered intermediary, your details are stored with a KRA such as CAMS KRA, CVL KRA, NDML, DotEx, or Karvy KRA. This means you do not need to repeat the full KYC process each time you approach a new intermediary — you only need to update or verify your existing record.

What should I do if my KYC is rejected?
If your KYC is rejected, you will receive a rejection letter specifying the reason. Common reasons include blurry document scans, signature mismatch, name discrepancy between PAN and Aadhaar, or address proof being more than 3 months old. You must re-submit with corrected documents. Call our support team or visit a branch for guidance.

How do I check my KYC status?
You can check your KYC status on the websites of major KRAs by entering your PAN number. The status will show as KYC Registered, KYC Verified, KYC On Hold, or KYC Rejected. If your status is On Hold or Rejected, contact the KRA or your intermediary for further steps.

Is my KYC valid forever?
KYC registration does not expire, but re-KYC may be required periodically based on regulatory changes or if your details such as address, contact number, or photograph need to be updated. Always ensure your details are current to avoid transaction restrictions.

What happens during the onboarding consultation?
During your onboarding consultation with our advisor, you will discuss which investment products align with your financial goals, understand the documentation requirements specific to your account type, get guidance on completing the KYC process if you have not done so already, and review the terms and conditions for the services you wish to avail.
""",

    "sip_mandates": """
SIP and Mandate Setup — Frequently Asked Questions

What is a SIP?
A Systematic Investment Plan (SIP) is a method of investing a fixed amount of money at regular intervals — monthly, quarterly, or weekly — into a mutual fund scheme of your choice. SIPs are one of the most disciplined and popular ways to build wealth over time, as they benefit from rupee cost averaging and the power of compounding.

What is a mandate and why do I need one?
A mandate is an authorisation you give to your bank to automatically debit a specified amount from your account on a scheduled date and transfer it to your investment account. Without a registered mandate, each SIP instalment would require a manual payment, which defeats the purpose of systematic investing. A mandate makes the process automatic and ensures you never miss an instalment.

What types of mandates are available?
There are three common types of mandates:
NACH Mandate (National Automated Clearing House): The most commonly used. It allows automatic debit from your bank account on a specified date. Registration typically takes 20 to 30 days.
e-Mandate via Net Banking: A faster digital mandate linked to your online banking credentials. Usually activated within 1 to 5 working days.
e-Mandate via Debit Card: Uses your debit card details for mandate registration. Activation is typically within 1 to 3 working days.

What is the minimum SIP amount?
Most mutual fund schemes allow SIPs starting from as low as Rs 100 or Rs 500 per month. The minimum amount varies by fund house and scheme. There is no maximum limit, though very large SIPs may require additional documentation.

How do I register a SIP mandate?
To register a SIP mandate you will need your bank account details (account number, IFSC code), a cheque or your online banking credentials or debit card (depending on mandate type), your PAN card, and an active investment account. Our advisor will walk you through the step-by-step process during your consultation.

Can I change or cancel my SIP?
Yes. You can pause, modify, or cancel your SIP at any time, usually with effect from the next instalment date. To change the SIP amount or date, you typically need to cancel the existing SIP and register a new one. Some fund houses allow online modifications. Cancelling a SIP does not redeem your existing units — your invested amount remains in the fund.

What happens if my SIP instalment bounces?
If there are insufficient funds in your account on the SIP date, the instalment bounces. Most AMCs allow up to 2 or 3 consecutive bounces before discontinuing the SIP. You may also be charged a penalty by your bank for a bounced ECS or NACH debit. Ensure your account always has sufficient balance on or before the SIP debit date.

How long does mandate registration take?
NACH mandates typically take 20 to 30 working days to activate because physical forms need to pass through the banking system. e-Mandates via net banking or debit card are much faster, usually 1 to 5 working days. During the waiting period, your SIP instalments may need to be paid manually or via a one-time payment.

What should I prepare for the SIP consultation?
Before your consultation, please have ready your bank account number and IFSC code, your investment goals and approximate monthly investment amount, the investment horizon you have in mind, and any preference for equity, debt, or hybrid funds. Our advisor will help you match these details to the right fund and mandate type.

Can I set up multiple SIPs?
Yes. You can run multiple SIPs across different funds simultaneously. Each SIP can have a different amount, date, and fund. Running SIPs in funds of different categories (equity, debt, international) helps with diversification. Each SIP will have its own mandate.
""",

    "statements_tax": """
Statements and Tax Documents — Frequently Asked Questions

What types of statements can I request?
You can request the following types of statements:
Account Statement: Shows all transactions (purchases, redemptions, dividends) in your investment account over a selected period.
Portfolio Valuation Statement: Shows the current market value of all your holdings.
Capital Gains Statement: Shows the gains or losses from redemptions, segregated by short-term and long-term, for tax computation.
Dividend Statement: Shows all dividend payouts received during the year.
Consolidated Account Statement (CAS): A single statement covering investments across all mutual fund houses, sent monthly by CAMS or KFintech.

What is a Capital Gains Statement and when do I need it?
A Capital Gains Statement is a tax document that lists all units redeemed during the financial year and the resulting short-term or long-term capital gains or losses. You need this when filing your Income Tax Return (ITR). Gains from equity funds held less than 12 months are short-term (taxed at 15%), while gains from equity funds held over 12 months are long-term (taxed at 10% above Rs 1 lakh). Debt fund gains are taxed as per your income tax slab.

What is Form 26AS and why is it important?
Form 26AS is a consolidated tax credit statement issued by the Income Tax Department. It shows TDS (Tax Deducted at Source) deducted by fund houses on dividend payouts, advance tax paid, and self-assessment tax. You should always match your Form 26AS with the dividend statements from your funds before filing your ITR to avoid discrepancies.

How do I get my tax documents for ELSS investments?
ELSS (Equity Linked Savings Scheme) investments qualify for a deduction under Section 80C of the Income Tax Act, up to Rs 1.5 lakh per year. To claim this, you need a purchase statement or investment receipt showing the amount invested in ELSS during the financial year. This is available from your AMC or investment platform account statement.

When are statements available for the financial year?
For the financial year April to March, most AMCs release the Capital Gains Statement and consolidated statements by mid-April for the previous year's transactions. Some platforms make them available immediately after March 31. Always download your statements before the ITR filing deadline.

How do I request a statement?
You can request statements online through the AMC website or app, through the investment platform or distributor portal, by emailing or calling the AMC's customer service, or by visiting a branch. During your consultation, our advisor can guide you to the right portal and help you download the relevant documents.

What is TDS on mutual fund dividends?
Since the Finance Act 2020, dividends from mutual funds are taxed in the hands of the investor at their applicable income tax slab rate. If your total dividend income from a fund house exceeds Rs 5,000 in a financial year, the fund house deducts TDS at 10%. This TDS is reflected in your Form 26AS and can be claimed as a credit when filing your ITR.

What documents should I bring to the tax statement consultation?
Please have your PAN number, your investment account login credentials, the financial year for which you need the statement, and a list of all fund houses or platforms where you have investments. Our advisor will help you locate all relevant documents and explain how to use them for tax filing.

How do I calculate my net tax liability from mutual fund gains?
To calculate tax: list all redemptions made in the year, classify gains as short-term or long-term based on holding period, apply the relevant tax rate, subtract the Rs 1 lakh long-term capital gains exemption for equity funds, and add the net taxable gain to your total income for ITR calculation. Our advisor can walk you through this calculation with your actual statements.
""",

    "withdrawals": """
Withdrawals and Redemption Timelines — Frequently Asked Questions

How do I redeem my mutual fund investments?
You can redeem mutual fund units by placing a redemption request through the AMC website or app, through the investment platform or distributor, or by submitting a physical redemption form at the AMC branch. You can choose to redeem a specific number of units, a specific rupee amount, or all units. The request is typically processed within one to two business days.

When will the money reach my bank account?
The timeline depends on the fund type:
Liquid and Overnight Funds: T+1 business day (next business day after request).
Debt Funds (Short-term, Ultra Short-term): T+2 business days.
Equity Funds (including ELSS): T+3 business days.
International Funds: T+3 to T+7 business days, depending on underlying market settlement.
Note: T is the day on which the redemption request is submitted before the fund cut-off time (usually 3 PM for most funds).

What is the cut-off time for same-day NAV?
For equity and hybrid funds, the cut-off time is 3 PM IST. Requests received before 3 PM are processed at the same day's NAV. Requests after 3 PM are processed at the next business day's NAV. For liquid funds, the cut-off is 1:30 PM to 2 PM, varying by fund.

Is there any exit load on redemptions?
Exit load is a small fee charged on redemptions made before a specified holding period. Most equity funds charge 1% exit load if redeemed within 1 year of investment. Many liquid and debt funds have zero exit load after a short holding period of 7 to 15 days. Always check the scheme information document (SID) for the exit load applicable to your specific fund.

What is ELSS lock-in and when can I redeem?
ELSS funds have a mandatory 3-year lock-in period from the date of each SIP instalment. You cannot redeem ELSS units before 3 years. Each instalment has its own lock-in clock. After 3 years, the units are freely redeemable with no exit load.

Can I do a partial redemption?
Yes. You can redeem part of your holdings while keeping the rest invested. You specify either a rupee amount or a number of units to redeem. The remaining units continue to be invested and earn returns.

What bank account will the redemption proceeds go to?
Redemption proceeds are always credited to the bank account registered in your investment folio. This is a security measure. If you have changed your bank account, you must update it with the fund house before placing a redemption request. Updating bank details may take 5 to 7 business days.

What should I prepare for the withdrawal consultation?
Before your consultation, have your investment folio number or account login, the approximate redemption amount or specific fund you want to redeem, your registered bank account details, and any tax implications you want to discuss (especially for equity funds held for over a year). Our advisor will guide you through the process and flag any exit loads or tax liabilities.

Can I withdraw if my KYC is not updated?
If your KYC has lapsed, is on hold, or needs re-verification, you may face restrictions on redemptions. It is important to keep your KYC details current, especially your address, contact number, and bank account details. If you face a KYC-related hold on your account, contact our support team immediately.
""",

    "account_changes": """
Account Changes, Nominee Updates and Profile Changes — Frequently Asked Questions

How do I update my address in my investment account?
To update your address, submit a written request with your signature, a copy of your updated address proof (utility bill, Aadhaar, bank statement — not older than 3 months), and your PAN card. You can submit this at an AMC branch, through the distributor's portal, or by mailing a signed form. Address changes typically take 7 to 10 business days to reflect across all folios.

How do I add or change a nominee?
A nominee is the person who receives your investments in case of your demise. To add or change a nominee, you need to submit a Nomination Form (SBI/AMC specific), signed by you and attested by a witness. You will need the nominee's name, address, date of birth, and relationship to you. For minor nominees, a guardian's details are also required. Nomination changes take 5 to 7 business days.

What happens if I have not registered a nominee?
If you have not registered a nominee and you pass away, your investments become part of your estate. The legal heirs must go through a legal succession process, including submitting a probate or succession certificate, to claim the investments. This process is lengthy and may take months or even years. It is strongly recommended to register a nominee for every folio.

How do I update my mobile number and email address?
Your mobile number and email address are used for OTP authentication and communication. To update these, you typically need to submit a request through the AMC's online portal (if linked with Aadhaar), by visiting a branch with identity proof, or by submitting a signed request form. Mobile number changes may require OTP verification on both the old and new number.

Can I change my bank account linked to investments?
Yes. To change the registered bank account: submit a Bank Mandate Change Form, attach a cancelled cheque or bank statement for the new account, and provide identity proof. The old account remains active for any pending transactions during the processing period (7 to 15 business days). For security, the first redemption after a bank change may require an additional waiting period of 10 business days.

How do I change the name on my investment account?
Name changes (due to marriage, spelling corrections, or legal name change) require submission of a Name Change Request Form, documentary evidence such as a marriage certificate or court order, updated PAN card (if name changed on PAN), and updated Aadhaar. Name changes are processed by the KRA and take 15 to 20 business days.

What is a joint account and how do I add or remove a joint holder?
Mutual fund folios can be held jointly by up to three individuals. The first holder is the primary account holder. To add or remove a joint holder, you typically need to close the existing folio and open a new one — this involves redeeming units from the old folio and reinvesting in the new joint folio. Our advisor can guide you through this process.

What documents should I bring for the account changes consultation?
Depending on the change you need:
For address change: new address proof and PAN card.
For nominee change: nominee's details and a witness.
For bank account change: cancelled cheque and identity proof.
For mobile or email update: identity proof.
For name change: marriage certificate or court order, updated PAN and Aadhaar.
Our advisor will confirm exactly what is needed for your specific situation during the consultation.

How long do account changes typically take to process?
Processing times vary by type of change and AMC:
Address or contact update: 5 to 10 business days.
Nominee change: 5 to 7 business days.
Bank account change: 7 to 15 business days (with an additional 10-day redemption freeze).
Name change: 15 to 20 business days.
Joint holder changes: varies significantly, as a new folio must be created.
""",
}

TOPIC_KEYS = list(SAMPLE_FAQ.keys())


def scrape_topic(topic_key: str, output_dir: str, url: str | None = None) -> list[str]:
    """
    Write FAQ text for topic_key to output_dir.
    If url is provided, fetches and parses that page (requires httpx + bs4).
    Falls back to built-in sample content otherwise.
    """
    topic_dir = os.path.join(output_dir, topic_key)
    os.makedirs(topic_dir, exist_ok=True)
    created = []

    if url:
        try:
            import httpx
            from bs4 import BeautifulSoup

            print(f"  Fetching {url} ...")
            response = httpx.get(url, timeout=10, follow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            text = soup.get_text(separator="\n", strip=True)
            if len(text) < 100:
                raise ValueError("Page content too short — falling back to sample data")
            out_path = os.path.join(topic_dir, "scraped.txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            created.append(out_path)
            print(f"  Saved scraped content -> {out_path}")
            return created
        except Exception as exc:
            print(f"  Scraping failed ({exc}). Using built-in sample data.")

    # Built-in sample content
    content = SAMPLE_FAQ.get(topic_key)
    if not content:
        print(f"  No sample data for topic: {topic_key}")
        return created

    out_path = os.path.join(topic_dir, f"{topic_key}_faq.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content.strip())
    created.append(out_path)
    print(f"  Saved sample FAQ -> {out_path}")
    return created


def main():
    parser = argparse.ArgumentParser(description="Scrape / generate FAQ text files for RAG pipeline.")
    parser.add_argument(
        "--topic",
        choices=TOPIC_KEYS + ["all"],
        default="all",
        help="Topic key to scrape, or 'all' for every topic.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw_docs"),
        help="Output directory (default: data/raw_docs relative to project root).",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Optional URL to scrape for the chosen topic. Falls back to built-in data on failure.",
    )
    args = parser.parse_args()

    topics = TOPIC_KEYS if args.topic == "all" else [args.topic]
    total_files = []
    for t in topics:
        print(f"Processing topic: {t}")
        files = scrape_topic(t, args.output, url=args.url if len(topics) == 1 else None)
        total_files.extend(files)

    print(f"\nDone. {len(total_files)} file(s) created.")


if __name__ == "__main__":
    main()
