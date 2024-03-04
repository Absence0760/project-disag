# disag

## Overview

This tool facilitates the analysis and manipulation of water flow data from two input files. The process involves handling monthly and daily values, ensuring synchronization of dates, performing exceedance calculations, and generating new files with matched exceedance values. Additionally, the tool converts daily numbers to percentages and creates new daily values based on the calculated percentages. Finally, the tool converts the data from millions of cubic meters per day to cubic meters per second, with a special code (-99) indicating no data.

## Instructions

1. **Select two input files:**
   - Monthly values (millions cubic meters/month)
   - Daily values (cubic meters/second) representing the flow rate in cubic meters passing per second.

   Ensure that the dates in both files start at the same year and month for accurate analysis.

2. **Run the tool to perform the following steps:**

   a. Separate exceedance values from both files and create new files.

   b. Match exceedance values considering millions of cubic meters per month.

   c. Convert daily numbers to percentages.

   d. Generate new daily values based on the calculated percentages.

   e. Convert from millions of cubic meters per day to cubic meters per second.

   *Note: The code -99 is used to denote instances with no available data.*

## Example

Here is a step-by-step example with screenshots:

FILES:
.DAY and .MON

## Keywords

- Daily flow and monthly flow
- Disaggregation
- Flow duration curve
- Exceedence curve (string of data without being linked to a date)
- 12 exceedence curves.

## How to Use

1. Clone the repository to your local machine:

   ```bash
   git clone git@github.com:Absence0760/disag.git
