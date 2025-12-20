Build the container and its environment using:
```powershell
docker-compose up -d --build
```

The 1000 requests sample log file is self-contained inside the container (because it contains the "tool archive"), so you can just run this command to see the results on Windows as csv files:
```powershell
docker exec -it fifa_processor_container python3 /data/direct_parser.py ita_public_tools/input/test_log.gz
```

But, if you want to work with the entire dataset, you should download a specific day and place it inside the working dir on Windows (this command below downloads the data for day #6 of the WorldCup):

```powershell
curl -o wc_day6_1.gz ftp://ita.ee.lbl.gov/traces/WorldCup/wc_day6_1.gz
```

Then, you can run this command to see the results of that day (day #6 in this case):

```powershell
docker exec -it fifa_processor_container python3 /data/direct_parser.py /data/wc_day6_1.gz
```

The code will make 2 files named as `name-of-the-dataset-file.csv` and `name-of-the-dataset-file-bursts.csv`. The second csv file contains the requests count for each minute in that day.