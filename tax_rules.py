"""Tax rules for estimating the tax rate on interest (tax year 2026).

Only used by the "Estimate my tax rates" section. All amounts are dollars;
rates are fractions (0.22 = 22%). Brackets are [start of bracket, rate] on
taxable income. Filing status keys: "single", "married" (married filing
jointly), "head" (head of household; states without their own head-of-
household figures use the single ones).

Update these once a year.

Sources:
- Federal: IRS Revenue Procedure 2025-32 (2026 inflation adjustments, with the
  One Big Beautiful Bill Act changes), https://www.irs.gov/pub/irs-drop/rp-25-32.pdf.
  Net Investment Income Tax thresholds (not indexed): IRS Questions and
  Answers on the Net Investment Income Tax.
- States: Tax Foundation, Janelle Fritts and Katherine Loughead, "State
  Individual Income Tax Rates and Brackets, 2026" (February 17, 2026; data as
  of February 11, 2026), https://taxfoundation.org/data/all/state/state-income-tax-rates-2026/
  (CC BY-NC 4.0). Single and married brackets, standard deductions and
  personal exemptions. Credits (for example California's exemption credit or
  Utah's standard-deduction credit) are left out: a fixed credit doesn't
  change the rate on extra income.
  Georgia and South Carolina cut their rates after the table was published;
  both are updated from their revenue departments (see below the table).
  Cross-checked against the official 2026 sources:
  - New York: NYS Department of Taxation and Finance, IT-2105-I (2026),
    https://www.tax.ny.gov/pdf/2026/inc/it2105i_2026.pdf (matches; head of
    household brackets and standard deduction added from it).
  - New Jersey: 2026 NJ-1040-ES instructions,
    https://www.nj.gov/treasury/taxation/pdf/current/1040esi.pdf (matches;
    head of household uses Table B, the married table).
  - California: the Franchise Tax Board hasn't published 2026 schedules; its
    2026 Form 540-ES instructions use the 2025 schedules and standard
    deduction, https://www.ftb.ca.gov/forms/2025/2025-540-tax-rate-schedules.pdf.
    Brackets match the Tax Foundation; the standard deduction is the FTB's
    $5,706 / $11,412 (the Tax Foundation shows $5,540 / $11,080). Head of
    household (Schedule Z) added, with the 1% Behavioral Health Services Tax
    over $1,000,000.
- New York City and Yonkers: IT-2105-I (2026), above. NYC taxes New York
  taxable income; Yonkers residents pay 16.75% of their net New York State tax.
- County taxes (shown as a range only): Maryland, Comptroller of Maryland,
  2026 state and local withholding memo (February 4, 2026),
  https://www.marylandcomptroller.gov/content/dam/mdcomp/md/state-payroll/memos/2026/2026-maryland-state-and-local-withholding-information.pdf;
  Indiana, Department of Revenue Departmental Notice #1,
  https://www.in.gov/dor/files/dn01.pdf.

Known simplifications: no phase-outs of deductions, exemptions or credits,
no benefit recapture (New York, Connecticut), no Minnesota or Vermont
surtaxes, dividends and capital gains taxed like other income by every state,
and no local taxes other than New York City and Yonkers.
"""

TAX_RULES_YEAR = 2026

FEDERAL = {
    "brackets": {
        "single": [[0, 0.10], [12_400, 0.12], [50_400, 0.22], [105_700, 0.24], [201_775, 0.32],
                   [256_225, 0.35], [640_600, 0.37]],
        "married": [[0, 0.10], [24_800, 0.12], [100_800, 0.22], [211_400, 0.24], [403_550, 0.32],
                    [512_450, 0.35], [768_700, 0.37]],
        "head": [[0, 0.10], [17_700, 0.12], [67_450, 0.22], [105_700, 0.24], [201_750, 0.32],
                 [256_200, 0.35], [640_600, 0.37]],
    },
    "standard_deduction": {"single": 16_100, "married": 32_200, "head": 24_150},
    # Qualified dividends and long-term capital gains: 0%, then 15%, then 20%.
    "gains_brackets": {
        "single": [[0, 0.0], [49_450, 0.15], [545_500, 0.20]],
        "married": [[0, 0.0], [98_900, 0.15], [613_700, 0.20]],
        "head": [[0, 0.0], [66_200, 0.15], [579_600, 0.20]],
    },
    "niit_rate": 0.038,  # Net Investment Income Tax
    "niit_threshold": {"single": 200_000, "married": 250_000, "head": 200_000},
}

# Tax Foundation 2026 table (see the top of this file).
STATES = {
    "Alabama": {
        "brackets": {"single": [[0, 0.02], [500, 0.04], [3000, 0.05]], "married": [[0, 0.02], [1000, 0.04], [6000, 0.05]]},
        "standard_deduction": {"single": 3000, "married": 8500},
        "exemption": {"single": 1500, "married": 3000},
    },
    "Alaska": {
        "brackets": {"single": [], "married": []},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 0, "married": 0},
    },
    "Arizona": {
        "brackets": {"single": [[0, 0.025]], "married": [[0, 0.025]]},
        "standard_deduction": {"single": 8350, "married": 16700},
        "exemption": {"single": 0, "married": 0},
    },
    "Arkansas": {
        "brackets": {"single": [[0, 0.02], [4600, 0.039]], "married": [[0, 0.02], [4600, 0.039]]},
        "standard_deduction": {"single": 2470, "married": 4940},
        "exemption": {"single": 0, "married": 0},
    },
    "California": {
        "brackets": {"single": [[0, 0.01], [11079, 0.02], [26264, 0.04], [41452, 0.06], [57542, 0.08], [72724, 0.093], [371479, 0.103], [445771, 0.113], [742953, 0.123], [1000000, 0.133]], "married": [[0, 0.01], [22158, 0.02], [52528, 0.04], [82904, 0.06], [115084, 0.08], [145448, 0.093], [742958, 0.103], [891542, 0.113], [1000000, 0.123], [1485906, 0.133]]},
        "standard_deduction": {"single": 5540, "married": 11080},
        "exemption": {"single": 0, "married": 0},
    },
    "Colorado": {
        "brackets": {"single": [[0, 0.044]], "married": [[0, 0.044]]},
        "standard_deduction": {"single": 16100, "married": 32200},
        "exemption": {"single": 0, "married": 0},
    },
    "Connecticut": {
        "brackets": {"single": [[0, 0.02], [10000, 0.045], [50000, 0.055], [100000, 0.06], [200000, 0.065], [250000, 0.069], [500000, 0.0699]], "married": [[0, 0.02], [20000, 0.045], [100000, 0.055], [200000, 0.06], [400000, 0.065], [500000, 0.069], [1000000, 0.0699]]},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 15000, "married": 24000},
    },
    "Delaware": {
        "brackets": {"single": [[0, 0.0], [2000, 0.022], [5000, 0.039], [10000, 0.048], [20000, 0.052], [25000, 0.0555], [60000, 0.066]], "married": [[0, 0.0], [2000, 0.022], [5000, 0.039], [10000, 0.048], [20000, 0.052], [25000, 0.0555], [60000, 0.066]]},
        "standard_deduction": {"single": 3250, "married": 6500},
        "exemption": {"single": 0, "married": 0},
    },
    "Florida": {
        "brackets": {"single": [], "married": []},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 0, "married": 0},
    },
    "Georgia": {
        "brackets": {"single": [[0, 0.0519]], "married": [[0, 0.0519]]},
        "standard_deduction": {"single": 12000, "married": 24000},
        "exemption": {"single": 0, "married": 0},
    },
    "Hawaii": {
        "brackets": {"single": [[0, 0.014], [9600, 0.032], [14400, 0.055], [19200, 0.064], [24000, 0.068], [36000, 0.072], [48000, 0.076], [125000, 0.079], [175000, 0.0825], [225000, 0.09], [275000, 0.1], [325000, 0.11]], "married": [[0, 0.014], [19200, 0.032], [28800, 0.055], [38400, 0.064], [48000, 0.068], [72000, 0.072], [96000, 0.076], [250000, 0.079], [350000, 0.0825], [450000, 0.09], [550000, 0.1], [650000, 0.11]]},
        "standard_deduction": {"single": 4400, "married": 8800},
        "exemption": {"single": 1144, "married": 2288},
    },
    "Idaho": {
        "brackets": {"single": [[0, 0.0], [4811, 0.053]], "married": [[0, 0.0], [9622, 0.053]]},
        "standard_deduction": {"single": 16100, "married": 32200},
        "exemption": {"single": 0, "married": 0},
    },
    "Illinois": {
        "brackets": {"single": [[0, 0.0495]], "married": [[0, 0.0495]]},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 2925, "married": 5850},
    },
    "Indiana": {
        "brackets": {"single": [[0, 0.0295]], "married": [[0, 0.0295]]},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 1000, "married": 2000},
    },
    "Iowa": {
        "brackets": {"single": [[0, 0.038]], "married": [[0, 0.038]]},
        "standard_deduction": {"single": 16100, "married": 32200},
        "exemption": {"single": 0, "married": 0},
    },
    "Kansas": {
        "brackets": {"single": [[0, 0.052], [23000, 0.0558]], "married": [[0, 0.052], [46000, 0.0558]]},
        "standard_deduction": {"single": 3605, "married": 8240},
        "exemption": {"single": 9160, "married": 18320},
    },
    "Kentucky": {
        "brackets": {"single": [[0, 0.035]], "married": [[0, 0.035]]},
        "standard_deduction": {"single": 3360, "married": 3360},
        "exemption": {"single": 0, "married": 0},
    },
    "Louisiana": {
        "brackets": {"single": [[0, 0.03]], "married": [[0, 0.03]]},
        "standard_deduction": {"single": 12875, "married": 25750},
        "exemption": {"single": 0, "married": 0},
    },
    "Maine": {
        "brackets": {"single": [[0, 0.058], [27399, 0.0675], [64849, 0.0715]], "married": [[0, 0.058], [54849, 0.0675], [129749, 0.0715]]},
        "standard_deduction": {"single": 8350, "married": 16700},
        "exemption": {"single": 5300, "married": 10600},
    },
    "Maryland": {
        "brackets": {"single": [[0, 0.02], [1000, 0.03], [2000, 0.04], [3000, 0.0475], [100000, 0.05], [125000, 0.0525], [150000, 0.055], [250000, 0.0575], [500000, 0.0625], [1000000, 0.065]], "married": [[0, 0.02], [1000, 0.03], [2000, 0.04], [3000, 0.0475], [150000, 0.05], [175000, 0.0525], [225000, 0.055], [300000, 0.0575], [600000, 0.0625], [1200000, 0.065]]},
        "standard_deduction": {"single": 3350, "married": 6700},
        "exemption": {"single": 3200, "married": 6400},
    },
    "Massachusetts": {
        "brackets": {"single": [[0, 0.05], [1083150, 0.09]], "married": [[0, 0.05], [1083150, 0.09]]},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 4400, "married": 8800},
    },
    "Michigan": {
        "brackets": {"single": [[0, 0.0425]], "married": [[0, 0.0425]]},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 5900, "married": 11800},
    },
    "Minnesota": {
        "brackets": {"single": [[0, 0.0535], [33310, 0.068], [109430, 0.0785], [203150, 0.0985]], "married": [[0, 0.0535], [48700, 0.068], [193480, 0.0785], [337930, 0.0985]]},
        "standard_deduction": {"single": 15300, "married": 30600},
        "exemption": {"single": 0, "married": 0},
    },
    "Mississippi": {
        "brackets": {"single": [[0, 0.0], [10000, 0.04]], "married": [[0, 0.0], [10000, 0.04]]},
        "standard_deduction": {"single": 2300, "married": 4600},
        "exemption": {"single": 6000, "married": 12000},
    },
    "Missouri": {
        "brackets": {"single": [[0, 0.0], [1348, 0.02], [2696, 0.025], [4044, 0.03], [5392, 0.035], [6740, 0.04], [8088, 0.045], [9436, 0.047]], "married": [[0, 0.0], [1348, 0.02], [2696, 0.025], [4044, 0.03], [5392, 0.035], [6740, 0.04], [8088, 0.045], [9436, 0.047]]},
        "standard_deduction": {"single": 16100, "married": 32200},
        "exemption": {"single": 0, "married": 0},
    },
    "Montana": {
        "brackets": {"single": [[0, 0.047], [47500, 0.0565]], "married": [[0, 0.047], [95000, 0.0565]]},
        "standard_deduction": {"single": 16100, "married": 32200},
        "exemption": {"single": 0, "married": 0},
    },
    "Nebraska": {
        "brackets": {"single": [[0, 0.0246], [4130, 0.0351], [24760, 0.0455]], "married": [[0, 0.0246], [8250, 0.0351], [49530, 0.0455]]},
        "standard_deduction": {"single": 8850, "married": 17700},
        "exemption": {"single": 0, "married": 0},
    },
    "Nevada": {
        "brackets": {"single": [], "married": []},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 0, "married": 0},
    },
    "New Hampshire": {
        "brackets": {"single": [], "married": []},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 0, "married": 0},
    },
    "New Jersey": {
        "brackets": {"single": [[0, 0.014], [20000, 0.0175], [35000, 0.035], [40000, 0.05525], [75000, 0.0637], [500000, 0.0897], [1000000, 0.1075]], "married": [[0, 0.014], [20000, 0.0175], [50000, 0.0245], [70000, 0.035], [80000, 0.05525], [150000, 0.0637], [500000, 0.0897], [1000000, 0.1075]]},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 1000, "married": 2000},
    },
    "New Mexico": {
        "brackets": {"single": [[0, 0.015], [5500, 0.032], [16500, 0.043], [33500, 0.047], [66500, 0.049], [210000, 0.059]], "married": [[0, 0.015], [8000, 0.032], [25000, 0.043], [50000, 0.047], [100000, 0.049], [315000, 0.059]]},
        "standard_deduction": {"single": 16100, "married": 32200},
        "exemption": {"single": 0, "married": 0},
    },
    "New York": {
        "brackets": {"single": [[0, 0.039], [8500, 0.044], [11700, 0.0515], [13900, 0.054], [80650, 0.059], [215400, 0.0685], [1077550, 0.0965], [5000000, 0.103], [25000000, 0.109]], "married": [[0, 0.039], [17150, 0.044], [23600, 0.0515], [27900, 0.054], [161550, 0.059], [323200, 0.0685], [2155350, 0.0965], [5000000, 0.103], [25000000, 0.109]]},
        "standard_deduction": {"single": 8000, "married": 16050},
        "exemption": {"single": 0, "married": 0},
    },
    "North Carolina": {
        "brackets": {"single": [[0, 0.0399]], "married": [[0, 0.0399]]},
        "standard_deduction": {"single": 12750, "married": 25500},
        "exemption": {"single": 0, "married": 0},
    },
    "North Dakota": {
        "brackets": {"single": [[0, 0.0], [48475, 0.0195], [244825, 0.025]], "married": [[0, 0.0], [80975, 0.0195], [298075, 0.025]]},
        "standard_deduction": {"single": 16100, "married": 32200},
        "exemption": {"single": 0, "married": 0},
    },
    "Ohio": {
        "brackets": {"single": [[0, 0.0], [26050, 0.0275]], "married": [[0, 0.0], [26050, 0.0275]]},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 2400, "married": 4800},
    },
    "Oklahoma": {
        "brackets": {"single": [[0, 0.0], [3750, 0.025], [4900, 0.035], [7200, 0.045]], "married": [[0, 0.0], [7500, 0.025], [9800, 0.035], [14400, 0.045]]},
        "standard_deduction": {"single": 6350, "married": 12700},
        "exemption": {"single": 1000, "married": 2000},
    },
    "Oregon": {
        "brackets": {"single": [[0, 0.0475], [4550, 0.0675], [11400, 0.0875], [125000, 0.099]], "married": [[0, 0.0475], [9100, 0.0675], [22800, 0.0875], [250000, 0.099]]},
        "standard_deduction": {"single": 2910, "married": 5820},
        "exemption": {"single": 0, "married": 0},
    },
    "Pennsylvania": {
        "brackets": {"single": [[0, 0.0307]], "married": [[0, 0.0307]]},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 0, "married": 0},
    },
    "Rhode Island": {
        "brackets": {"single": [[0, 0.0375], [82050, 0.0475], [186450, 0.0599]], "married": [[0, 0.0375], [82050, 0.0475], [186450, 0.0599]]},
        "standard_deduction": {"single": 11200, "married": 22400},
        "exemption": {"single": 5250, "married": 10500},
    },
    "South Carolina": {
        "brackets": {"single": [[0, 0.0], [3640, 0.03], [18230, 0.06]], "married": [[0, 0.0], [3640, 0.03], [18230, 0.06]]},
        "standard_deduction": {"single": 8350, "married": 16700},
        "exemption": {"single": 0, "married": 0},
    },
    "South Dakota": {
        "brackets": {"single": [], "married": []},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 0, "married": 0},
    },
    "Tennessee": {
        "brackets": {"single": [], "married": []},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 0, "married": 0},
    },
    "Texas": {
        "brackets": {"single": [], "married": []},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 0, "married": 0},
    },
    "Utah": {
        "brackets": {"single": [[0, 0.045]], "married": [[0, 0.045]]},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 0, "married": 0},
    },
    "Vermont": {
        "brackets": {"single": [[0, 0.0335], [49400, 0.066], [119700, 0.076], [249700, 0.0875]], "married": [[0, 0.0335], [82500, 0.066], [199450, 0.076], [304000, 0.0875]]},
        "standard_deduction": {"single": 7650, "married": 15300},
        "exemption": {"single": 5300, "married": 10600},
    },
    "Virginia": {
        "brackets": {"single": [[0, 0.02], [3000, 0.03], [5000, 0.05], [17000, 0.0575]], "married": [[0, 0.02], [3000, 0.03], [5000, 0.05], [17000, 0.0575]]},
        "standard_deduction": {"single": 8750, "married": 17500},
        "exemption": {"single": 930, "married": 1860},
    },
    "Washington": {
        "brackets": {"single": [], "married": []},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 0, "married": 0},
    },
    "West Virginia": {
        "brackets": {"single": [[0, 0.0222], [10000, 0.0296], [25000, 0.0333], [40000, 0.0444], [60000, 0.0482]], "married": [[0, 0.0222], [10000, 0.0296], [25000, 0.0333], [40000, 0.0444], [60000, 0.0482]]},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 2000, "married": 4000},
    },
    "Wisconsin": {
        "brackets": {"single": [[0, 0.035], [15110, 0.044], [51950, 0.053], [332720, 0.0765]], "married": [[0, 0.035], [20150, 0.044], [69260, 0.053], [443630, 0.0765]]},
        "standard_deduction": {"single": 13960, "married": 25840},
        "exemption": {"single": 700, "married": 1400},
    },
    "Wyoming": {
        "brackets": {"single": [], "married": []},
        "standard_deduction": {"single": 0, "married": 0},
        "exemption": {"single": 0, "married": 0},
    },
    "District of Columbia": {
        "brackets": {"single": [[0, 0.04], [10000, 0.06], [40000, 0.065], [60000, 0.085], [250000, 0.0925], [500000, 0.0975], [1000000, 0.1075]], "married": [[0, 0.04], [10000, 0.06], [40000, 0.065], [60000, 0.085], [250000, 0.0925], [500000, 0.0975], [1000000, 0.1075]]},
        "standard_deduction": {"single": 16100, "married": 32200},
        "exemption": {"single": 0, "married": 0},
    },
}

# Official cross-checks (see the top of this file).
STATES["California"]["brackets"]["head"] = [
    [0, 0.01], [22_173, 0.02], [52_530, 0.04], [67_716, 0.06], [83_805, 0.08], [98_990, 0.093],
    [505_208, 0.103], [606_251, 0.113], [1_000_000, 0.123], [1_010_417, 0.133],  # +1% over $1M
]
STATES["California"]["standard_deduction"] = {"single": 5_706, "married": 11_412, "head": 11_412}
STATES["New York"]["brackets"]["head"] = [
    [0, 0.039], [12_800, 0.044], [17_650, 0.0515], [20_900, 0.054], [107_650, 0.059],
    [269_300, 0.0685], [1_616_450, 0.0965], [5_000_000, 0.103], [25_000_000, 0.109],
]
STATES["New York"]["standard_deduction"]["head"] = 11_200
STATES["New Jersey"]["brackets"]["head"] = STATES["New Jersey"]["brackets"]["married"]  # Table B

# Laws passed after the Tax Foundation table (February 2026), from the official sources:
# - Georgia, H.B. 463 (signed May 11, 2026, for 2026): flat 4.99% (was 5.19%); standard deduction
#   $15,000 single and head of household, $30,000 married filing jointly (was $12,000 / $24,000).
#   Georgia Department of Revenue, "Important Tax Updates",
#   https://dor.georgia.gov/taxes/important-tax-updates
STATES["Georgia"]["brackets"] = {"single": [[0, 0.0499]], "married": [[0, 0.0499]]}
STATES["Georgia"]["standard_deduction"] = {"single": 15_000, "married": 30_000, "head": 15_000}
# - South Carolina, H. 4216 (signed March 30, 2026, from tax year 2026): 1.99% on taxable income
#   under $30,000 and 5.21% above (was 0% / 3% / 6%), the same for every filing status; the
#   federal standard deduction is replaced by the South Carolina Income Adjusted Deduction:
#   $15,000 single, $22,500 head of household, $30,000 married filing jointly (it is reduced at
#   higher incomes; that reduction is left out, like other phase-outs).
#   South Carolina Department of Revenue, "Information about H. 4216",
#   https://dor.sc.gov/news/information-about-h-4216
STATES["South Carolina"]["brackets"] = {"single": [[0, 0.0199], [30_000, 0.0521]],
                                        "married": [[0, 0.0199], [30_000, 0.0521]]}
STATES["South Carolina"]["standard_deduction"] = {"single": 15_000, "married": 30_000, "head": 22_500}

# New York City: brackets on New York taxable income.
NYC = {
    "single": [[0, 0.03078], [12_000, 0.03762], [25_000, 0.03819], [50_000, 0.03876]],
    "married": [[0, 0.03078], [21_600, 0.03762], [45_000, 0.03819], [90_000, 0.03876]],
    "head": [[0, 0.03078], [14_400, 0.03762], [30_000, 0.03819], [60_000, 0.03876]],
}
YONKERS_RATE = 0.1675  # share of net New York State tax

# County income taxes that also apply to interest: lowest and highest county rate, in %.
COUNTY_RANGES = {"Maryland": (2.25, 3.30), "Indiana": (0.50, 3.00)}
COUNTY_SOURCES = {
    "Maryland": ("Comptroller of Maryland", "https://www.marylandcomptroller.gov/content/dam/mdcomp/md/"
                 "state-payroll/memos/2026/2026-maryland-state-and-local-withholding-information.pdf"),
    "Indiana": ("Indiana Department of Revenue", "https://www.in.gov/dor/files/dn01.pdf"),
}

TAX_RULES = {
    "year": TAX_RULES_YEAR,
    "federal": FEDERAL,
    "states": STATES,
    "nyc": NYC,
    "yonkers_rate": YONKERS_RATE,
    "county_ranges": COUNTY_RANGES,
}
