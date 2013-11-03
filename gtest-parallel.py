#!/usr/bin/env python2
import Queue
import optparse
import subprocess
import sys
import threading

class FilterFormat:
  total_tests = 0
  finished_tests = 0

  tests = {}
  last_finished_test = ""
  outputs = {}
  failures = []

  def print_test_status(self):
    print "[%d/%d] %s" % (self.finished_tests,
                          self.total_tests,
                          self.last_finished_test)

  def handle_meta(self, job_id, args):
    global total_tests, finished_tests, last_finished_test
    (command, arg) = args.split(' ', 1)
    if command == "TEST":
      (binary, test) = arg.split(' ', 1)
      self.tests[job_id] = (binary, test.strip())
      self.outputs[job_id] = []
      self.total_tests += 1
    elif command == "EXIT":
      exit_code = int(arg.strip())
      self.finished_tests += 1
      (binary, test) = self.tests[job_id]
      self.last_finished_test = test
      if exit_code != 0:
        self.failures.append(self.tests[job_id])
        for line in self.outputs[job_id]:
          print line
      self.print_test_status()

  def add_stdout(self, job_id, output):
    self.outputs[job_id].append(output)

  def log(self):
    while True:
      line = log.get()
      if line == "":
        break
      (prefix, output) = line.split(' ', 1)

      if prefix[-1] == ':':
        self.handle_meta(int(prefix[:-1]), output)
      else:
        self.add_stdout(int(prefix[:-1]), output)
    if self.failures:
      print "FAILED TESTS (" + str(len(self.failures)) + "):"
      for (binary, test) in self.failures:
        print " ", binary + ": " + test

class RawFormat:
  def log(self):
    while True:
      line = log.get()
      if line == "":
        return
      sys.stdout.write(line + "\n")
      sys.stdout.flush()

parser = optparse.OptionParser(
    usage = 'usage: %prog [options] executable [executable ...]')

parser.add_option('-w', '--workers', type='int', default=16,
                  help='number of workers to spawn')
parser.add_option('--gtest_filter', type='string', default='',
                  help='test filter')
parser.add_option('--gtest_also_run_disabled_tests', action='store_true',
                  default=False, help='run disabled tests too')
parser.add_option('--format', type='string', default='filter',
                  help='output format (raw,filter)')

(options, binaries) = parser.parse_args()

if binaries == []:
  parser.print_usage()
  sys.exit(1)

log = Queue.Queue()
tests = Queue.Queue()

logger = RawFormat()
if options.format == 'raw':
  pass
elif options.format == 'filter':
  logger = FilterFormat()
else:
  sys.exit("Unknown output format: " + options.format)

# Find tests.
job_id = 0
for test_binary in binaries:
  command = [test_binary]
  if options.gtest_filter != '':
    command += ['--gtest_filter=' + options.gtest_filter]
  if options.gtest_also_run_disabled_tests:
    command += ['--gtest_also_run_disabled_tests']

  test_list = subprocess.Popen(command + ['--gtest_list_tests'],
                               stdout=subprocess.PIPE).communicate()[0]

  test_group = ''
  for line in test_list.split('\n'):
    if not line.strip():
      continue
    if line[0] != " ":
      test_group = line.strip()
      continue
    line = line.strip()
    if not options.gtest_also_run_disabled_tests and 'DISABLED' in line:
      continue

    test = test_group + line
    tests.put((command, job_id, test))
    log.put(str(job_id) + ': TEST ' + test_binary + ' ' + test)
    job_id += 1

exit_code = 0
def run_job((command, job_id, test)):
  sub = subprocess.Popen(command + ['--gtest_filter=' + test],
                         stdout = subprocess.PIPE,
                         stderr = subprocess.STDOUT)

  while True:
    line = sub.stdout.readline()
    if line == '':
      break
    log.put(str(job_id) + '> ' + line.rstrip())

  code = sub.wait()
  log.put(str(job_id) + ': EXIT ' + str(code))
  if code != 0:
    global exit_code
    exit_code = code

def worker():
  while True:
    try:
      run_job(tests.get_nowait())
      tests.task_done()
    except Queue.Empty:
      return

def start_daemon(func):
  t = threading.Thread(target=func)
  t.daemon = True
  t.start()
  return t

workers = [start_daemon(worker) for i in range(options.workers)]
printer = start_daemon(logger.log)

[t.join() for t in workers]
log.put("")
printer.join()
sys.exit(exit_code)
