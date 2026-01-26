#!/usr/bin/env python
"""Test script for vanpool roster tools."""

import json

from pool_patrol_tools import get_vanpool_roster, get_vanpool_info, list_vanpools


def main():
    print("=" * 60)
    print("Testing Vanpool Tools (Database-backed)")
    print("=" * 60)

    # Test 1: List all vanpools
    print("\n1. Listing all vanpools...")
    result = list_vanpools.invoke({})
    print(f"   Total vanpools: {result['count']}")
    for vp in result["vanpools"][:3]:  # Show first 3
        print(f"      - {vp['vanpool_id']}: {vp['work_site']} ({vp['rider_count']} riders)")
    if result["count"] > 3:
        print(f"      ... and {result['count'] - 3} more")

    # Test 2: Get vanpool info
    print("\n2. Getting info for VP-101...")
    result = get_vanpool_info.invoke({"vanpool_id": "VP-101"})
    print(f"   Vanpool: {result['vanpool_id']}")
    print(f"   Work Site: {result['work_site']}")
    print(f"   Address: {result['work_site_address']}")
    print(f"   Capacity: {result['capacity']}")
    print(f"   Rider Count: {result['rider_count']}")

    # Test 3: Get roster for VP-101
    print("\n3. Getting roster for VP-101...")
    result = get_vanpool_roster.invoke({"vanpool_id": "VP-101"})
    print(f"   Vanpool: {result['vanpool_id']}")
    print(f"   Rider Count: {result['rider_count']}")
    print("   Riders:")
    for rider in result["riders"]:
        name = f"{rider.get('first_name', '?')} {rider.get('last_name', '?')}"
        home_zip = rider.get("home_zip", "?")
        shift_id = rider.get("shift_id", "?")
        print(f"      - {name} (ZIP: {home_zip}, Shift: {shift_id})")

    # Test 4: Get roster for VP-102 (has some suspicious employees)
    print("\n4. Getting roster for VP-102...")
    result = get_vanpool_roster.invoke({"vanpool_id": "VP-102"})
    print(f"   Vanpool: {result['vanpool_id']}")
    print(f"   Rider Count: {result['rider_count']}")
    for rider in result["riders"]:
        name = f"{rider.get('first_name', '?')} {rider.get('last_name', '?')}"
        home_zip = rider.get("home_zip", "?")
        print(f"      - {name} (ZIP: {home_zip})")

    # Test 5: Invalid vanpool
    print("\n5. Testing invalid vanpool ID...")
    result = get_vanpool_roster.invoke({"vanpool_id": "VP-999"})
    print(f"   Result: {result}")

    # Show tool metadata (what the LLM sees)
    print("\n" + "=" * 60)
    print("Tool Metadata (what the LLM sees):")
    print("=" * 60)
    print(f"Name: {get_vanpool_roster.name}")
    print(f"Description: {get_vanpool_roster.description[:100]}...")


if __name__ == "__main__":
    main()
