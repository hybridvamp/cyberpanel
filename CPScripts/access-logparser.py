#!/usr/bin/python
# -*- coding: utf-8 -*-
# Originally based on code from: https://leancrew.com/all-this/2013/07/parsing-my-apache-logs/

import os
import re
import sys
import time
from collections import Counter
from datetime import date, timedelta
from datetime import datetime
from os.path import join, isfile


# print('version is', sys.version)


def main():
    script = sys.argv[0]
    # filename = sys.argv[2]
    # filenametest = "/home/example.com.access_log"
    # username = 'server'
    username = str(sys.argv[1])
    # Define the day of interest in the Apache common log format.
    try:
        daysago = int(sys.argv[2])
        # daysago = 4
    except:
        daysago = 0
    the_day = date.today() - timedelta(daysago)
    apache_day = the_day.strftime('[%d/%b/%Y:')
    dcpumon_day = the_day.strftime('%Y/%b/%d')

    # Set variables to empty
    controlpanel = ''
    domlogs_path = ''

    try:
        if os.path.isfile('/usr/local/cpanel/cpanel') | os.path.isfile(os.getcwd() + '/cpanel'):
            controlpanel = 'cpanel'
            datetime_dcpumon = date.today().strftime('%Y/%b/%d')  # 2020/Feb/10
            # Current Dcpumon file
            dcpumon_current_log = "/var/log/dcpumon/" + datetime_dcpumon  # /var/log/dcpumon/2019/Feb/15
            acesslog_sed = "-ssl_log"
            if username == 'server':
                domlogs_path = '/usr/local/apache/domlogs/'
            else:
                user_homedir = "/home/" + username
                user_accesslogs = "/home/" + username + "/logs/"
                domlogs_path = "/usr/local/apache/domlogs/" + username

        elif os.path.isfile('/usr/bin/cyberpanel') | os.path.isfile(os.getcwd() + '/cyberpanel'):
            controlpanel = 'cyberpanel'
            acesslog_sed = ".access_log"
            if username == 'server':
                # Needs updated to glob all /home/*/logs/
                domlogs_path = '/home/username/Desktop/domlogs'
            else:
                # Get users homedir path
                user_homedir = os.path.expanduser("~" + username)
                domlogs_path = user_homedir + "/logs/"

    except:
        controlpanel = 'Control Panel not found'

    # Define Output file
    stats_output = open(os.getcwd() + '/stats.txt', "w")

    # Define log path directory
    path = domlogs_path

    # path = "/home/username/Desktop/domlogs"

    # Get list of dir contents
    logs_path_contents = os.listdir(path)

    # Get list of files only from this directory
    logs = filter(lambda f: isfile(join(path, f)), logs_path_contents)

    # Regex for the Apache common log format.
    parts = [  # host %h  			:ip/hostname of the client 	172.68.142.138
        # indent %l (unused) 	:client identity via client's identd configuration 	-
        # user %u 			:HTTP authenticated user ID 	-
        # time %t 			:timestamp 	[09/Mar/2019:00:38:03 -0600]
        # request "%r" 		:request method of request, resource requested, & protocol 	"POST /wp-login.php HTTP/1.1"
        # status %>s 		:Apache status code 	404
        # size %b (careful,can be'-'):size of request in bytes, excluding headers 	3767
        # referrer "%{Referer}i"	:Referer 	"https://www.google.com/"
        # user agent "%{User-agent}i":User-Agent 	"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36 SE 2.X MetaSr 1.0"
        r'(?P<host>\S+)',
        r'\S+',
        r'(?P<user>\S+)',
        r'\[(?P<time>.+)\]',
        r'"(?P<request>.*)"',
        r'(?P<status>[0-9]+)',
        r'(?P<size>\S+)',
        r'"(?P<referrer>.*)"',
        r'"(?P<agent>.*)"',
    ]
    pattern = re.compile(r'\s+'.join(parts) + r'\s*\Z')

    # Regex for a feed request.
    feed = re.compile(r'/all-this/(\d\d\d\d/\d\d/[^/]+/)?feed/(atom/)?')

    # Regexes for internal and Google search referrers.

    internal = re.compile(r'https?://(www\.)?example\.com.*')
    google = re.compile(r'https?://(www\.)?google\..*')

    # Regexes for Uptime Monitoring Robots
    uptimeroboturl = re.compile(r'https?://(www\.)?uptimerobot\..*')
    uptimerobot = re.compile(r'UptimeRobot')

    # Change Apache log items into Python types.

    def pythonized(d):
        # Clean up the request.

        d['request'] = d['request'].split()[1]

        # Some dashes become None.

        for k in ('user', 'referrer', 'agent'):
            if d[k] == '-':
                d[k] = None

        # The size dash becomes 0.

        if d['size'] == '-':
            d['size'] = 0
        else:
            d['size'] = int(d['size'])

        # Convert the timestamp into a datetime object. Accept the server's time zone.

        (time, zone) = d['time'].split()
        d['time'] = datetime.strptime(time, '%d/%b/%Y:%H:%M:%S')

        return d

    # Is this hit a page?

    def ispage(hit):
        # Failures and redirects.

        hit['status'] = int(hit['status'])
        if hit['status'] < 200 or hit['status'] >= 300:
            return False

        # Feed requests.

        if feed.search(hit['request']):
            return False

        # Requests that aren't GET.

        #    if (hit['request'])[0:3] != 'GET':
        #        return False

        # Images, sounds, etc.

        if hit['request'].split()[1][-1] != '/':
            return False

        # Requests that aren't Head type. AKA uptime monitoring

        if (hit['request'])[0:3] == 'HEAD':
            return False

        # Must be a page.

        return True

    # Is the referrer interesting? Internal and Google referrers are not.
    def goodref(hit):
        if hit['referrer']:
            return not (google.search(hit['referrer'])
                        or internal.search(hit['referrer']))
        else:
            return False

    # Is the user agent interesting? An uptime monitoring robot is not.
    def goodagent(hit):
        if hit['agent']:
            return not (uptimerobot.search(hit['agent'])
                        or uptimeroboturl.search(hit['agent']))
        else:
            return False

    # create a function which returns the value of a dictionary
    def keyfunction(k):
        return d[k]

    # Initialize pages for top IP's

    pages = []

    # Initialize dictionaries for hit counters
    wp_login_dict = {}
    wp_cron_dict = {}
    wp_xmlrpc_dict = {}
    wp_admin_ajax_dict = {}

    # Parse all the lines associated with the day of interest.

    for log in logs:
        file = os.path.join(path, log)
        text = open(file, "r")
        wp_login_hit_count = 0
        wp_cron_hit_count = 0
        wp_xmlrpc_hit_count = 0
        wp_admin_ajax_hit_count = 0
        for line in text:
            if apache_day in line:
                if re.match("(.*)(wp-login.php)(.*)", line):
                    wp_login_hit_count = wp_login_hit_count + 1
                if re.match("(.*)(wp-cron.php)(.*)", line):
                    wp_cron_hit_count = wp_cron_hit_count + 1
                if re.match("(.*)(xmlrpc.php)(.*)", line):
                    wp_xmlrpc_hit_count = wp_xmlrpc_hit_count + 1
                if re.match("(.*)(admin-ajax.php)(.*)", line):
                    wp_admin_ajax_hit_count = wp_admin_ajax_hit_count + 1
                m = pattern.match(line)
                hit = m.groupdict()
                if ispage(hit):
                    pages.append(pythonized(hit))
                else:
                    continue
        # print >> stats_output, log + "|" + line,
        # print(log + "|" + line, end="", file=stats_output)

        log = log.replace('-ssl_log', '', 1)
        log = log.replace('.access_log', '', 1)

        wp_login_dict[log] = int(wp_login_hit_count)
        wp_cron_dict[log] = int(wp_cron_hit_count)
        wp_xmlrpc_dict[log] = int(wp_xmlrpc_hit_count)
        wp_admin_ajax_dict[log] = int(wp_admin_ajax_hit_count)

        #    print(log)
        #    print("Wordpress Logins => " + str(wp_login_hit_count))
        #    print("Wordpress wp-cron => " + str(wp_cron_hit_count))
        #    print("Wordpress xmlrpc => " + str(wp_xmlrpc_hit_count))
        #    print("Wordpress admin-ajax => " + str(wp_admin_ajax_hit_count))
        #    print("===============================================================")
        text.close()
    # print(pages, file=stats_output)

    print('          ')
    print('============================================')
    print('Snapshot for ' + username)
    print(time.strftime('%H:%M%p %Z on %b %d, %Y'))
    if controlpanel == 'cpanel' or controlpanel == 'cyberpanel':
        print(controlpanel + " detected")
    else:
        print('No control Panel detected')

    print('Accesslog path used: ' + path)
    # print(dcpumon_current_log)

    # Show the top five pages and the total.
    print('''
    Show top 10 pages %s''' % the_day.strftime('%b %d, %Y'))
    pageviews = Counter(x['request'] for x in pages if goodagent(x))
    pagestop10 = pageviews.most_common(10)
    for p in pagestop10:
        print('  %5d  %s' % p[::-1])
    print('  %5d  total' % len(pages))
    print('============================================')

    # Show the top five referrers.
    print('''
    Show top 10 referrers %s''' % the_day.strftime('%b %d, %Y'))
    referrers = Counter(x['referrer'] for x in pages if goodref(x))
    referrerstop10 = referrers.most_common(10)
    for r in referrerstop10:
        print('  %5d  %s' % r[::-1])
    print('  %5d  total' % sum(referrers.values()))
    print('============================================')
    # Show the top 10 IPs.
    print('''
    Show Top 10 IPs %s''' % the_day.strftime('%b %d, %Y'))
    iphits = Counter(x['host'] for x in pages if goodagent(x))
    iptop10 = iphits.most_common(10)
    for p in iptop10:
        print('  %5d  %s' % p[::-1])
    print('  %5d  total hits' % sum(iphits.values()))
    print('============================================')

    # CMS Checks

    print('          ')
    print('CMS Checks')
    print('          ')

    print('Wordpress Checks')
    print('============================================')

    d = wp_login_dict
    # print(d)
    print('''Wordpress Bruteforce Logins for wp-login.php %s''' % the_day.strftime('%b %d, %Y'))
    print('          ')
    # sort by dictionary by the values and print top 10 {key, value} pairs
    for key in sorted(d, key=keyfunction, reverse=True)[:10]:
        print('  %5d  %s' % (d[key], key))
    print('  %5d  total hits' % sum(dict.values(d)))
    print('          ')

    d = wp_cron_dict

    print('''Wordpress Cron wp-cron.php(virtual cron) checks for %s''' % the_day.strftime('%b %d, %Y'))
    print('          ')
    # sort by dictionary by the values and print top 10 {key, value} pairs
    for key in sorted(d, key=keyfunction, reverse=True)[:10]:
        print('  %5d  %s' % (d[key], key))
    print('  %5d  total hits' % sum(dict.values(d)))
    print('          ')

    d = wp_xmlrpc_dict

    print('''Wordpress XMLRPC Attacks checks for xmlrpc.php for %s''' % the_day.strftime('%b %d, %Y'))
    print('          ')
    # sort by dictionary by the values and print top 10 {key, value} pairs
    for key in sorted(d, key=keyfunction, reverse=True)[:10]:
        print('  %5d  %s' % (d[key], key))
    print('  %5d  total hits' % sum(dict.values(d)))
    print('          ')

    d = wp_admin_ajax_dict

    print('''Wordpress Heartbeat API checks for admin-ajax.php for %s''' % the_day.strftime('%b %d, %Y'))
    print('          ')
    # sort by dictionary by the values and print top 10 {key, value} pairs
    for key in sorted(d, key=keyfunction, reverse=True)[:10]:
        print('  %5d  %s' % (d[key], key))
    print('  %5d  total hits' % sum(dict.values(d)))
    print('============================================')


if __name__ == '__main__':
    main()