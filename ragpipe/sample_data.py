"""Generates FICTIONAL raw 'state standards' text in a consistent page format, so the extractor has something to parse.
All states, fees, deadlines and rule numbers are invented; they are not real DMV or hospital regulations.

Page format (one file per state):
    STATE: Northvale
    SECTION: Vehicle Registration
    RULE NV-1.1: Annual registration fee
    Body text ... (may span several lines)
    Updated: 2025-03-01
"""
import random

STATES = ["Northvale", "Eastmoor", "Southridge", "Westbrook", "Lakeshore", "Highfield", "Riverton", "Stonebay"]
SECTIONS = {
    "Vehicle Registration": [("Annual registration fee", "The annual registration fee for a passenger vehicle is ${fee}. Renewal is due within {days} days of expiry."),
                             ("Late renewal penalty", "A late renewal incurs a penalty of ${fee} plus {days} days of grace before enforcement."),
                             ("Transfer of ownership", "Ownership must be transferred within {days} days of sale. The transfer fee is ${fee}.")],
    "Driver Licensing": [("Licence renewal period", "A standard licence is valid for {years} years. Renewal costs ${fee} and may be completed online."),
                         ("Knowledge test", "Applicants must pass the written knowledge test with at least {pct}% correct. A retest costs ${fee}."),
                         ("Vision requirements", "Applicants must have corrected vision of at least 20/{pct}. A vision screening is done at the counter.")],
    "Hospital Facility Codes": [("Facility licence renewal", "Hospital facility licences renew every {years} years. The renewal fee is ${fee} per licensed bed unit."),
                                ("Emergency department classification", "Emergency departments are classified into levels 1 to 4. Level 1 requires {days} hour continuous physician coverage."),
                                ("Inspection frequency", "Licensed hospitals are inspected every {years} years, or within {days} days of a serious complaint.")],
    "Commercial Vehicles": [("Weight limits", "The maximum gross vehicle weight without a special permit is {fee}00 kilograms."),
                            ("Driver hours", "Commercial drivers may drive at most {days} hours per week and must rest {pct} minutes after 4 hours.")],
}

