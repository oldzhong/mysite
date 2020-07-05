# -*- coding: utf-8 -*-

import logging
import json
import re
from datetime import datetime, timedelta
import time

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum, Min, Q

from myssg.utils import ItemUtils
from tms.models import ClockItem


class Command(BaseCommand):
    help = 'Import clock items'

    def handle(self, *args, **options):
        logging.error('Begin to import clock items')
        logging.warning('Begin to delete all clock items first')
        ClockItem.objects.all().delete()
        logging.warning('Success to delete all clock items')
        agenda_file_paths = ['/Users/zy/github/elvestar/msv4/time/time.org']
        agenda_file_paths.extend([
            '/Users/zy/github/elvestar/msv4/time/home.org',
            '/Users/zy/github/elvestar/msv4/time/2015.org',
            '/Users/zy/github/elvestar/msv4/time/2016.org',
            '/Users/zy/github/elvestar/msv4/time/2017.org',
            '/Users/zy/github/elvestar/msv4/time/2018.org',
            '/Users/zy/github/elvestar/msv4/time/2019.org',
        ])
        process_org_agenda(agenda_file_paths)
        export_time_usage()


def process_org_agenda(agenda_file_paths):
    unfinished_clock_count = 0
    for agenda_file_path in agenda_file_paths:
        h1 = 'null h1'
        h2 = 'null h2'
        headline = 'null headline'
        level = 0
        for line in file(agenda_file_path):
            headline_regex = '^(?P<stars>\*+) (?P<headline>.*)$'
            m1 = re.match(headline_regex, line)
            if m1 is not None:
                # print line,
                level = len(m1.groupdict()['stars'])
                headline = m1.groupdict()['headline']
                if level == 1:
                    h1 = headline
                elif level == 2:
                    h2 = headline
            else:
                clock_regex = '^ +CLOCK: \[(?P<start_clock>.+)\]--\[(?P<end_clock>.+)\] =>.+'
                unfinished_clock_regex = '^ +CLOCK: \[(?P<start_clock>.+)\]'
                m2 = re.match(clock_regex, line)
                m3 = re.match(unfinished_clock_regex, line)
                if m2 is not None or m3 is not None:
                    if m2 is not None:
                        start_clock_str = m2.groupdict()['start_clock']
                        end_clock_str = m2.groupdict()['end_clock']
                        start_time = datetime.strptime(start_clock_str[0:10] + ' ' + start_clock_str[-5:],
                                                       '%Y-%m-%d %H:%M')
                        end_time = datetime.strptime(end_clock_str[0:10] + ' ' + end_clock_str[-5:],
                                                     '%Y-%m-%d %H:%M')
                    else:
                        unfinished_clock_count += 1
                        if unfinished_clock_count > 1:
                            print('Find another unfinished clock item! It is impossible. '
                                  'Clock item: %s in file %s' % (line, agenda_file_path))
                            return False

                        start_clock_str = m3.groupdict()['start_clock']
                        start_time = datetime.strptime(start_clock_str[0:10] + ' ' + start_clock_str[-5:],
                                                       '%Y-%m-%d %H:%M')
                        end_time = datetime.now()
                    # print(end_clock_str)
                    # print(start_clock_str)
                    date = start_time.date()
                    iso_year, week, weekday = date.isocalendar()
                    time_cost_min = (end_time - start_time).total_seconds() / 60
                    clock_item = ClockItem(
                        start_time=start_time,
                        end_time=end_time,
                        start_hour=start_time.hour,
                        end_hour=end_time.hour,
                        date=date,
                        year=date.year,
                        month=date.month,
                        iso_year=iso_year,
                        week=week,
                        weekday=weekday,

                        thing=headline,
                        level=level,
                        category=h1,
                        project=h2,
                        time_cost_min=time_cost_min)
                    clock_item.save()
                else:
                    print('Find an unmatched clock item. '
                          'Clock item: %s in file %s' % (line, agenda_file_path))

    return True


def export_time_usage():
    start_date = datetime.now() - timedelta(days=366)
    stay_up_range = range(2, 6)
    quert_set = ClockItem.objects.filter(date__gte=start_date).exclude(category__in=['生活']). \
        values('date').annotate(tc_sum=Sum('time_cost_min'))
    stay_up_stats = ClockItem.objects.filter(Q(date__gte=start_date) &
                                             (Q(start_hour__in=stay_up_range) | Q(end_hour__in=stay_up_range))). \
        values('date').annotate(count=Count('thing'))
    time_usage = dict()
    for row in quert_set:
        ts_str = str(int(time.mktime(row['date'].timetuple())))
        time_usage[ts_str] = row['tc_sum']
    for row in stay_up_stats:
        ts_str = str(int(time.mktime(row['date'].timetuple())))
        if ts_str in time_usage:
            time_usage[ts_str] += 10000
        else:
            time_usage[ts_str] = 10000

    path = '/Users/zy/github/elvestar/mysite/static/data/latest_time_usage.json'
    f = file(path, 'w')
    f.write(json.dumps(time_usage))
    f.close()
