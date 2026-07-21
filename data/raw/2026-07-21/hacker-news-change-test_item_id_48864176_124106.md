My two year old taught me constraint solving | Hacker News
Hacker News
new
|
past
|
comments
|
ask
|
show
|
jobs
|
submit
login




My two year old taught me constraint solving
(
thecomputersciencebook.com
)
81 points
by
bambataa
13 hours ago
|
hide
|
past
|
favorite
|
27 comments




help












hexasquid
6 hours ago
|
next
[–]








Incredible. My two-year-old forgets to include Lambek when lecturing on Curry-Howard-Lambek correspondence. Kids.






reply










wiredfool
3 hours ago
|
prev
|
next
[–]








Had something similar to this with the kids with Lego Duplo tracks, similar topology but the switches gave the system state. Going "backwards" through a switch set the train to return that direction when coming the other way.


So we had a goal to make the train do interesting behaviors, like cover the entire track autonomously, pushing the switches itself. The biggest run I remember was a 4 bit counter.


Kid is now entering his last year of CS + Maths degree, so I guess it checks out.






reply










olooney
9 hours ago
|
prev
|
next
[–]








I wrote several polyomino solvers for this project:


https://www.oranlooney.com/demos/soma-forest/


One of them used constraint solving with Z3, which was indeed reasonably fast. However, by far the fastest was a simple backtracking solver written in Rust which used bit twiddling to quickly test for intersections. For polyomino's in particular, this represents between 10x and 100x constant speed boost, depending on the size of board. There's no way to get that back with a smarter solver.






reply










dmoy
11 hours ago
|
prev
|
next
[–]








While similarly playing brio with a two year old, I thought about a different dimension not mentioned here - super loose tolerances make the search space really weird.


In true 2-year-old fashion, my kid would bend the rules as much as possible by literally forcing pieces to the edge of their tolerance to make things fit that shouldn't fit.  8 piece circle yea, cool, but with a sufficiently old brio set handed down for 40 years or whatever, you can totally make a 7 piece "circle" thing.


So I decided some day I'll craft an interview question out of that, to see if people can figure out a good way to map a set of pieces laid out with given tolerance ranges for piece, see if it can connect, etc.  Haven't thought about it enough to really polish it for an interview, but some day.






reply










bryanrasmussen
5 hours ago
|
parent
|
next
[–]








>if people can figure out a good way to map a set of pieces laid out with given tolerance ranges for piece


so you work in some space where extremely good visual understanding and ability to abstract in 3 dimensions is a prerequisite?






reply










RataNova
3 hours ago
|
parent
|
prev
|
next
[–]








That tolerance turns a clean combinatorial problem into a continuous one






reply










NuclearPM
4 hours ago
|
parent
|
prev
|
next
[–]








Why would that be a good interview question?






reply










akoboldfrying
10 hours ago
|
parent
|
prev
|
next
[–]








I immediately got nerd-sniped by this...


A heuristic could try all kinds of fun force-directed placement stuff. For an exact solver, I think your best bet would (unfortunately) be to finely quantise the possible positions and orientations of each piece, describe each piece by 2 sets of positioned unit vectors (the vectors in one set start at the centre positions of each "hole" and are directed towards the centre of the piece, the other set is similar but holds the "plug" positions and orientations), and say that a partial solution is feasible iff every "plug" position is sufficiently far from all other plugs, and either sufficiently far from all other holes or within some small tolerances (in terms of both distance and angle) of some other hole. Actually, you would probably also need to treat the piece body as a "nothing else can occupy these positions" constraint. I say "unfortunate" because the position and orientation grids would need to be very fine relative to the size of the pieces, leading to a large state space thus long running times.


I think it would be fun to look for solutions that maximise the "badness" (e.g., sum of distances between matched holes and plugs) :)






reply










elcaro
8 hours ago
|
prev
|
next
[–]








Similar article I read 10 years ago that covers some of the same ground, with some pretty SVG's as well.


http://strangelyconsistent.org/blog/train-tracks






reply










RataNova
3 hours ago
|
prev
|
next
[–]








The strongest insight here is that the SAT solver did not merely solve the same problem faster. It solved a better-formulated problem: choose the pieces as well as their placement.






reply










polivier
10 hours ago
|
prev
|
next
[–]








> When this solver backjumps, it forgets the failure as soon as it lands, so if the same dead end comes up in a different part of the search it gets rediscovered from scratch.


Modern solvers such as CP-SAT combine some SAT features with a CP solver, based of the work of Peter Stuckey I think.






reply










comrade1234
12 hours ago
|
prev
|
next
[–]








Yon should publish this on LinkedIn.






reply










akoboldfrying
11 hours ago
|
parent
|
next
[–]








Given my feelings about the quality of the... discourse... on LinkedIn, I can't tell if this is a genuine compliment or a fiercely backhanded one.






reply










momocowcow
1 hour ago
|
prev
|
next
[–]








brio sets are for children 3 years and older...






reply










zahlman
11 hours ago
|
prev
|
next
[–]








The kid doesn't seem to be doing any actual teaching here. Cool that a two-year-old can say "exponential", though, I guess.


> “Dada! Degree three. No Euler circuit.”


…Oh. Okay, fine, weird rhetorical device but you do you.






reply










efavdb
9 hours ago
|
prev
|
next
[–]








My three year old taught me something he saw on a YouTube video:  you can search through a maze and find your way out just by keeping your right hand on the wall at all times and continuing till exit.  Does a DFS.






reply










LeoPanthera
9 hours ago
|
parent
|
next
[–]








This only works for two dimensional mazes where both the entrance and exit are on an edge and there are no loops in the maze.


If you introduce a bridge, or a tunnel, or put the goal in the middle, you can get stuck in a loop.






reply










RataNova
3 hours ago
|
parent
|
prev
|
next
[–]








A nice case of an algorithm being easier to learn physically than abstractly






reply










CGamesPlay
9 hours ago
|
parent
|
prev
|
next
[–]








Throw a loop/island in the maze and see how your kid reacts.






reply










mohamedkoubaa
9 hours ago
|
parent
|
prev
|
next
[–]








I vaguely recall a windows screensaver that did this






reply










onaclov2000
10 hours ago
|
prev
|
next
[–]








I'll be honest, while it's possible the article is genuine,at some point I felt/realized it seemed like an ad for the book, and made the story feel like it was not genuine and more like a contrived example of why the book is so useful and not real (again, not claiming real vs not real,just the vibe I felt) so I stopped reading.






reply










Jtsummers
9 hours ago
|
parent
|
next
[–]








> I'll be honest, while it's possible the article is genuine


No, there's not really much chance of that:


>> “Dada, real planners use SAT and its relatives for timetabling, chip layout, and routing for the same reason.”






reply










akoboldfrying
5 hours ago
|
prev
|
next
[–]








Insidious "gift" idea: A set of wooden track pieces with lengths and join angles chosen such that no subset of them can form a closed loop. No matter what you try, it's always
just a little bit
off.






reply










hyperhello
12 hours ago
|
prev
|
next
[–]








Sometimes you have to prove you’re #1 Dad.






reply










mcphage
11 hours ago
|
prev
|
next
[–]








What year was your son born?  Nobody has said “Silly Billy” in 30 years, unless under the auspices of a duly appointed official.






reply










nwiswell
11 hours ago
|
parent
|
next
[–]








I associate that phrase with Dr. Henry Killinger


https://youtu.be/9FUik3QotBQ?si=27AcY47wLNov0Vzw






reply










charcircuit
10 hours ago
|
prev
[–]








This attempt at humble bragging about how smart your two year old is was not necessary for this article. There does not need to be a constant game of trying to 1 up other parents by bragging about how much farther ahead your kid is compared to others.






reply










Consider applying for YC's Fall 2026 batch!
Applications
are open till July 27.


Guidelines
|
FAQ
|
Lists
|
API
|
Security
|
Legal
|
Apply to YC
|
Contact




Search: