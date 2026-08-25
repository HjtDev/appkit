# Third-party notices

`appkit` ships zero runtime `dependencies` (docs/CONTRACT.md §22). The one piece of
third-party code it redistributes is vendored, not depended on, so its licence is reproduced
here in full per the MIT licence's attribution requirement.

## `jalaali-js` (Gregorian <-> Jalali arithmetic)

Vendored into `src/vendor/jalaali.ts`, ported from `jalaali-js` v1.2.8
(https://github.com/jalaali/jalaali-js) by Behrang Norouzinia. See `src/vendor/jalaali.ts`'s own
header comment and `docs/CONTRACT.md` §19 for provenance and the reasoning for vendoring instead
of depending on it.

```
MIT License

Copyright (c) 2020 Behrang Norouzinia

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
