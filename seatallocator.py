'Imports'

import argparse
import collections
import csv
import os
import sys


'Constants'

# Seating Sections
PRIORITY = 'Priority'
LIMITED_VIEW = 'Limited View'
SCREEN_ONLY = 'Screen Only'

# Locations Listing
LOCATIONS = { PRIORITY, LIMITED_VIEW, SCREEN_ONLY }

# The number of just-in-case seats reserved in each section.
RESERVED = {
	PRIORITY: 0,
	LIMITED_VIEW: 50,
	SCREEN_ONLY: 0
}

# The total number of seats that can be allocated in each section.
AVAILABLE = {
	PRIORITY: 7000 - RESERVED[PRIORITY],
	LIMITED_VIEW: 1800 - RESERVED[LIMITED_VIEW],
	SCREEN_ONLY: 5000 - RESERVED[SCREEN_ONLY]
}

# The number of seats guaranteed to each person in priority seating.
GUARANTEED_PRIORITY = 7


'Classes'

class SeatAllocation(object):
	'''
	This class holds data on a number of allocated seats, and the location
	where they are allocated.
	'''

	def __init__(self, seats, location):
		'''
		Initializes a seat allocation with a seat count, and the location of
		the seats.
		@param seats The number of seats being allocated.
		@param location The location where the seats are allocated.
		'''
		assert isinstance(seats, int), 'expected @seats to be an int'
		assert seats > 0, 'expected @seats to be at least 1'
		assert isinstance(location, str), 'expected @location to be a str'
		assert location in LOCATIONS, 'unknown location: {}'.format(location)
		self.seats = seats
		self.location = location

	def __repr__(self):
		return 'SeatAllocation(seats={}, location={})'.format(
				self.seats, self.location)

	def __str__(self):
		return repr(self)


class SeatRequest(object):
	'''
	This class represents a request for seating, and the seats that are
	allocated to fulfill the request.
	'''

	def __hash__(self):
		return self.studentID

	def __init__(self, requestTime, studentID, regular, extra):
		'''
		Initializes a seat request with the number of seats being requested.
		@param requestTime The time at which the request was made.
		@param studentID The ID of the student making the request.
		@param regular The number of regular seats requested.
		@param extra The number of extra seats requested.
		'''
		assert isinstance(requestTime, int), 'expected @requestTime to be an int'
		assert isinstance(studentID, int), 'expected @studentID to be an int'
		assert isinstance(regular, int), 'expected @regular to be an int'
		assert 1 <= regular <= GUARANTEED_PRIORITY, 'expected @regular to be '\
		'between 1 and {} inclusive'.format(GUARANTEED_PRIORITY)
		assert isinstance(extra, int), 'expected @extra to be an int'
		self.requestTime = requestTime
		self.studentID = studentID
		self.regular = regular
		self.extra = extra
		self.allocations = []
		self.fulfilled = False

	def __repr__(self):
		return 'SeatRequest(requestTime={}, studentID={}, regular={}, '\
		'extra={}, allocated={}, fulfilled={})'.format(
			self.requestTime,
			self.studentID,
			self.regular,
			self.extra,
			self.allocations,
			self.fulfilled
		)

	def __str__(self):
		return repr(self)

	def allocate(self, allocation):
		'''
		Adds a seat allocation to the request.
		@param allocation The allocation being added.
		'''
		assert isinstance(allocation, SeatAllocation), 'expected @allocation '\
		'to be a SeatAllocation'
		self.allocations.append(allocation)

	def collapse(self):
		'''
		Collapses a request into a list containing the following:
		- student ID
		- regular seats requested
		- extra seats requested
		- priority seats given
		- limited view seats given
		- screen-only seats given
		'''
		seats = {
			PRIORITY: 0,
			LIMITED_VIEW: 0,
			SCREEN_ONLY: 0
		}
		for allocation in self.allocations:
			seats[allocation.location] += allocation.seats
		return [
			self.studentID,
			self.regular,
			self.extra,
			seats[PRIORITY],
			seats[LIMITED_VIEW],
			seats[SCREEN_ONLY]
		]


'Helpers'

def _allocatePriority(requests):
	'''
	Orders the requests by in ascending order by the number of extra tickets
	requested, and allocates them seats in the priority area until it is full.
	@param requests The list of requests.
	'''
	assert isinstance(requests, list), 'expected @requests to be a list'
	requests.sort(key=lambda r: r.extra)
	for request in requests:
		if request.fulfilled:
			continue
		if AVAILABLE[PRIORITY] >= request.extra:
			seats = SeatAllocation(request.extra, PRIORITY)
			request.allocate(seats)
			request.fulfilled = True
			AVAILABLE[PRIORITY] -= request.extra

def _allocateSecondary(requests):
	'''
	Allocates the rest of the seats fairly, then seat people in FCFS order.
	@param requests The list of requests.
	'''
	assert isinstance(requests, list), 'expected @requests to be a list'
	requests.sort(key=lambda r: r.requestTime)

	# A map of tickets that have been set aside for a given request.
	tickets = collections.defaultdict(lambda: 0)

	# Allocate tickets until we run out.
	remaining = AVAILABLE[LIMITED_VIEW] + AVAILABLE[SCREEN_ONLY]
	while remaining > 0:
		given = 0
		for request in requests:
			if request.fulfilled:
				continue
			if tickets[request] < request.extra:
				tickets[request] += 1
				remaining -= 1
				given += 1
		if given == 0:
			break

	# Allocate seats in limited view.
	for request in requests:
		if request.fulfilled:
			continue
		if AVAILABLE[LIMITED_VIEW] >= tickets[request]:
			seats = SeatAllocation(tickets[request], LIMITED_VIEW)
			request.allocate(seats)
			request.fulfilled = True
			AVAILABLE[LIMITED_VIEW] -= tickets[request]

	# Allocate seats in screen-only view.
	for request in requests:
		if request.fulfilled:
			continue
		if AVAILABLE[SCREEN_ONLY] >= tickets[request]:
			seats = SeatAllocation(tickets[request], SCREEN_ONLY)
			request.allocate(seats)
			request.fulfilled = True
			AVAILABLE[SCREEN_ONLY] -= tickets[request]


'Runtime'

if __name__ == '__main__':

	# Get the command arguments.
	parser = argparse.ArgumentParser()
	parser.add_argument(
		'inputFile',
		help='the location of the input CSV'
	)
	parser.add_argument(
		'outputFile',
		help='the location where fulfilled seat requests will be written'
	)
	parser.add_argument(
		'skippedFile',
		help='the location where skipped requests will be written'
	)
	args = parser.parse_args()


	# Check that the input file exists.
	if not os.path.exists(args.inputFile):
		raise Exception('file not found: {}'.format(inputFile))

	# Keep track of the student IDs to make sure there are no duplicates.
	studentIDs = set()

	# Read the CSV into a list of seat requests.
	requests = []
	skipped = []
	with open(args.inputFile, 'r') as file:
		reader = csv.reader(file, delimiter=',', quotechar='"')

		# Skip the header row.
		next(reader)

		# Extract each row, and read it into a request.
		for requestRow in reader:
			studentID, attending, regular, extra, accomodated, accomodation = requestRow
			studentID = int(studentID)
			regular = int(regular)
			extra = int(extra)
			accomodated = int(accomodated)
			request = SeatRequest(0, studentID, regular, extra)

			# Ensure the student ID isn't a duplicate.
			if studentID in studentIDs:
				raise Exception('duplicate student ID: {}'.format(studentID))
			studentIDs.add(studentID)

			# If the request requires accomodations, skip it.
			if accomodated > 0:
				skipped.append(request)
			else:
				requests.append(request)

	# Stats on what was read.
	print('Read {} seat requests.'.format(len(requests)))
	print('Skipped {} requests.'.format(len(skipped)))
	total = 0
	for request in requests:
		total += request.regular + request.extra
	print('Total seats requested: {}'.format(total))

	# Give everyone their priority seats.
	for request in requests:
		seats = SeatAllocation(request.regular, PRIORITY)
		request.allocate(seats)
		AVAILABLE[PRIORITY] -= request.regular
		if request.extra == 0:
			request.fulfilled = True

	# Allocate seats to people in priority seating until it is full, then fill
	# up the secondary locations.
	_allocatePriority(requests)
	_allocateSecondary(requests)

	# Sort for output.
	requests.sort(key=lambda r: r.regular + r.extra)

	# Write the results.
	with open(args.outputFile, 'w') as file:
		writer = csv.writer(file)
		writer.writerow([
			'StudentID',
			'Regular',
			'Extra',
			'Priority',
			'LimitedView',
			'ScreenOnly'
		])
		for request in requests:
			writer.writerow(request.collapse())


	


