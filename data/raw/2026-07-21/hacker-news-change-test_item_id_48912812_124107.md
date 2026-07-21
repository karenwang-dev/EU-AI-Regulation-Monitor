How to pack ternary numbers in 8-bit bytes | Hacker News
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




How to pack ternary numbers in 8-bit bytes
(
compilade.net
)
16 points
by
JoshTriplett
3 hours ago
|
hide
|
past
|
favorite
|
9 comments




help












JoshTriplett
3 hours ago
|
next
[–]








It's impressive how close to optimal this is.


You can beat the efficiency of 5 trits in 8 bits (1.6) with as few as 17 trits in 27 bits (~1.588), but once you account for rounding up to a whole number of
bytes
for practical reasons, then beating the efficiency requires going to at least 111 trits in 176 bits (~1.586), or perhaps more practically for fast unpacking, 161 trits in 256 bits (~1.59).


At that level, even if you have, say, 27B trits, the more efficient encodings would save something like 38-45MB (theoretical limit ~48MB), likely at the cost of some slowdown.






reply










jjgreen
1 hour ago
|
prev
|
next
[–]








Possible application:
https://thedailywtf.com/articles/What_Is_Truth_0x3f_






reply










benj111
1 hour ago
|
parent
|
next
[–]








Off the top of my head. Compilers. You may know that a value has known 1s and 0s and unknowns. This would allow you to represent that for optimisation purposes.






reply










Imustaskforhelp
3 minutes ago
|
root
|
parent
|
next
[–]








Arturo[0] language supports true,false and maybe. I really liked that idea actually, worth mentioning here.


so valid arturo code can be like (picked from their in-a-nutshell documentation)


i1: true


i2: false


i3: maybe


[0]:
https://arturo-lang.io/documentation/in-a-nutshell






reply










mi_lk
1 hour ago
|
parent
|
prev
|
next
[–]








Had a good chuckle






reply










kleton
1 hour ago
|
prev
|
next
[–]








Would this imply that the matrices should have dimensions of multiples of 40?






reply










Joker_vD
1 hour ago
|
prev
[–]








> Fixed point numbers to the rescue!


> a diagram that shows that dividing 0x7F (127) by 243 and then multiplying by 256 results in 0x86 (134)
> Tada!


How... how does that help with anything?


> Now digits can be easily extracted from the top two bits of the resulting 10-bit number when multiplying this 8-bit byte by 3.


What? Why? How? This is supposed to be the most insightful part of the post, and it's literally just "Behold!" from that one proof of Pythagorean theorem. Could someone please elaborate it for a non-genius like me?






reply










Tepix
57 minutes ago
|
parent
|
next
[–]








If your pack_number function builds the number up, the standard way to break it down is by extracting the least significant digit first using modulo and division.
To get something that works well with SIMD we need a different approach.
Instead of extracting the least significant digit from the bottom of an integer, we extract the most significant digit from the top of a fraction.


1. Convert to a fixed-point fraction: We scale our integer N into a fixed-point representation (e.g., using a 32-bit integer to represent the fraction). We do this by multiplying N by a precomputed reciprocal of 243.


2. Multiply by the base: Multiply the fraction by 3.


3. Extract: The integer portion of the result is your most significant trit.


4. Mask: Keep only the fractional remainder, and repeat.


The only operations here are multiplication, bitwise shift, and bitwise AND, i.e. perfectly suited for SIMD.


(in step 1 we replace the division with a multiplication by using the reciprocal. SIMD uses fixed-point integer arithmetic, not floating-point decimals)






reply










marginalia_nu
1 hour ago
|
parent
|
prev
[–]








If it's any consolation, I spent like two years of my life immersed in this field[1] and can still recite powers of three in the same way most nerds can only tell you powers of two, yet I still can't follow this floating point black magic.


[1] behold my misspent youth:
https://tunguska.sf.net/






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