// Package edge contains edge cases for testing Go extraction correctness.
// These patterns often break or confuse AST extractors.
package edge

import (
	"context"
	"fmt"
	"io"
	"sync"
	"time"
)

// ============================================================================
// INIT FUNCTIONS - Multiple init() in same file
// ============================================================================

var initOrder []string

func init() {
	initOrder = append(initOrder, "first")
}

func init() {
	initOrder = append(initOrder, "second")
}

func init() {
	initOrder = append(initOrder, "third")
}

// ============================================================================
// IOTA CONSTANTS - Complex iota patterns
// ============================================================================

type ByteSize int64

const (
	_           = iota             // Blank identifier with iota
	KB ByteSize = 1 << (10 * iota) // 1024
	MB                             // 1048576
	GB                             // 1073741824
	TB                             // 1099511627776
)

const (
	FlagRead  = 1 << iota // 1
	FlagWrite             // 2
	FlagExec              // 4
	FlagAll   = FlagRead | FlagWrite | FlagExec
)

// Iota reset in new const block
const (
	StateA = iota // 0
	StateB        // 1
	StateC        // 2
)

// ============================================================================
// BLANK IDENTIFIER PATTERNS
// ============================================================================

var _ io.Reader = (*BlankReader)(nil) // Interface compliance check

type BlankReader struct{}

func (BlankReader) Read(p []byte) (n int, err error) {
	return 0, io.EOF
}

// Blank in multiple assignment
func BlankMultiAssign() {
	_, b, _ := multiReturn()
	fmt.Println(b)
}

func multiReturn() (int, string, error) {
	return 1, "test", nil
}

// Blank in range
func BlankRange(items []string) {
	for _, item := range items {
		fmt.Println(item)
	}
	for i := range items {
		fmt.Println(i)
	}
}

// ============================================================================
// EMBEDDED TYPES AND PROMOTION
// ============================================================================

// Base type with methods
type Base struct {
	Name string
}

func (b *Base) BaseName() string {
	return b.Name
}

func (b *Base) Override() string {
	return "base"
}

// Embedded struct - promotes BaseName(), shadowed Override()
type Derived struct {
	*Base // Pointer embedding
	Value int
}

func (d *Derived) Override() string {
	return "derived: " + d.Base.Override() // Call shadowed method
}

// Double embedding
type DoubleDerived struct {
	Derived
	Extra string
}

// Interface embedding
type Reader interface {
	Read(p []byte) (n int, err error)
}

type Writer interface {
	Write(p []byte) (n int, err error)
}

type ReadWriter interface {
	Reader // Embedded interface
	Writer // Embedded interface
}

type Closer interface {
	Close() error
}

type ReadWriteCloser interface {
	ReadWriter // Nested embedded interface
	Closer
}

// ============================================================================
// NAMED RETURNS AND NAKED RETURNS
// ============================================================================

// Named return values
func NamedReturns(x int) (result int, err error) {
	if x < 0 {
		err = fmt.Errorf("negative value: %d", x)
		return // Naked return
	}
	result = x * 2
	return // Naked return with modified result
}

// Named returns with defer modification
func NamedReturnDefer() (result string) {
	defer func() {
		result = result + " (modified by defer)"
	}()
	result = "original"
	return // Defer modifies after return
}

// ============================================================================
// VARIADIC FUNCTIONS
// ============================================================================

// Basic variadic
func Variadic(prefix string, values ...int) int {
	sum := 0
	for _, v := range values {
		sum += v
	}
	return sum
}

// Variadic with interface
func VariadicInterface(format string, args ...interface{}) string {
	return fmt.Sprintf(format, args...)
}

// Passing slice to variadic
func PassSliceToVariadic() int {
	slice := []int{1, 2, 3, 4, 5}
	return Variadic("sum", slice...) // Spread operator
}

// ============================================================================
// TYPE ALIASES AND DEFINITIONS
// ============================================================================

// Type alias (same underlying type)
type MyInt = int

// Type definition (new type)
type NewInt int

// Method on defined type (allowed)
func (n NewInt) Double() NewInt {
	return n * 2
}

// Cannot add method to alias - this is a compile error:
// func (m MyInt) Triple() MyInt { return m * 3 }

// Generic type alias (Go 1.23+)
// type MySlice[T any] = []T

// ============================================================================
// METHOD VALUES VS METHOD EXPRESSIONS
// ============================================================================

type Counter struct {
	value int
	mu    sync.Mutex
}

func (c *Counter) Increment() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value++
}

func (c *Counter) Value() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.value
}

// Method value - bound to instance
func MethodValue() {
	c := &Counter{}

	// Method value - receiver is bound
	inc := c.Increment
	inc() // Calls c.Increment()
	inc() // Calls c.Increment() again
}

// Method expression - explicit receiver
func MethodExpression() {
	c := &Counter{}

	// Method expression - receiver as first argument
	inc := (*Counter).Increment
	inc(c) // Equivalent to c.Increment()

	// Can use with different instances
	c2 := &Counter{}
	inc(c2)
}

// ============================================================================
// COMPLEX CHANNEL PATTERNS
// ============================================================================

// Bidirectional channel
func Bidirectional(ch chan int) {
	ch <- 1
	<-ch
}

// Send-only channel
func SendOnly(ch chan<- int) {
	ch <- 1
}

// Receive-only channel
func ReceiveOnly(ch <-chan int) int {
	return <-ch
}

// Channel of channels
func ChannelOfChannels() {
	chOfCh := make(chan chan int)

	go func() {
		innerCh := make(chan int, 1)
		innerCh <- 42
		chOfCh <- innerCh
	}()

	received := <-chOfCh
	value := <-received
	fmt.Println(value)
}

// Nil channel behavior
func NilChannel() {
	var nilCh chan int // nil channel

	select {
	case <-nilCh:
		// Never executes - receive from nil blocks forever
	default:
		fmt.Println("default case")
	}
}

// Closed channel behavior
func ClosedChannel() {
	ch := make(chan int, 1)
	ch <- 1
	close(ch)

	// Can still receive
	v1, ok1 := <-ch // v1=1, ok1=true
	v2, ok2 := <-ch // v2=0, ok2=false (closed)

	fmt.Println(v1, ok1, v2, ok2)
}

// ============================================================================
// SELECT PATTERNS
// ============================================================================

// Select with default (non-blocking)
func SelectNonBlocking(ch chan int) (int, bool) {
	select {
	case v := <-ch:
		return v, true
	default:
		return 0, false
	}
}

// Select with timeout
func SelectTimeout(ch chan int, timeout time.Duration) (int, error) {
	select {
	case v := <-ch:
		return v, nil
	case <-time.After(timeout):
		return 0, fmt.Errorf("timeout after %v", timeout)
	}
}

// Select with context cancellation
func SelectContext(ctx context.Context, ch chan int) (int, error) {
	select {
	case v := <-ch:
		return v, nil
	case <-ctx.Done():
		return 0, ctx.Err()
	}
}

// Select with multiple cases of same channel type
func SelectMultipleSame(ch1, ch2, ch3 chan int) int {
	select {
	case v := <-ch1:
		return v
	case v := <-ch2:
		return v * 2
	case v := <-ch3:
		return v * 3
	}
}

// Empty select (blocks forever)
func SelectEmpty() {
	// select {} // Would block forever - commented out
}

// ============================================================================
// DEFER ORDERING AND EDGE CASES
// ============================================================================

// Defer LIFO order
func DeferOrder() []string {
	var result []string
	defer func() { result = append(result, "first") }()
	defer func() { result = append(result, "second") }()
	defer func() { result = append(result, "third") }()
	// Execution order: third, second, first
	return result
}

// Defer with loop (captures loop variable!)
func DeferInLoop() {
	for i := 0; i < 3; i++ {
		// BUG: All defers see i=3 (loop variable capture)
		defer fmt.Println("buggy:", i)
	}
}

// Defer with loop (fixed)
func DeferInLoopFixed() {
	for i := 0; i < 3; i++ {
		i := i // Shadow loop variable
		defer fmt.Println("fixed:", i)
	}
}

// Defer evaluates arguments immediately
func DeferArgEval() {
	x := 1
	defer fmt.Println("deferred x:", x) // Prints 1, not 2
	x = 2
}

// ============================================================================
// PANIC AND RECOVER PATTERNS
// ============================================================================

// Recover only works in deferred function
func RecoverPattern() (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("recovered: %v", r)
		}
	}()

	panic("something went wrong")
}

// Nested recover (only innermost catches)
func NestedRecover() {
	defer func() {
		if r := recover(); r != nil {
			fmt.Println("outer recover:", r)
		}
	}()

	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Println("inner recover:", r)
				panic("re-panic") // Re-panic for outer
			}
		}()
		panic("original panic")
	}()
}

// ============================================================================
// TYPE ASSERTION PATTERNS
// ============================================================================

// Type assertion with ok
func TypeAssertionOK(i interface{}) {
	if s, ok := i.(string); ok {
		fmt.Println("string:", s)
	}
}

// Type assertion panic (no ok)
func TypeAssertionPanic(i interface{}) string {
	return i.(string) // Panics if not string
}

// Type switch
func TypeSwitch(i interface{}) string {
	switch v := i.(type) {
	case nil:
		return "nil"
	case int:
		return fmt.Sprintf("int: %d", v)
	case string:
		return "string: " + v
	case bool:
		if v {
			return "true"
		}
		return "false"
	case []int:
		return fmt.Sprintf("[]int with %d elements", len(v))
	case map[string]int:
		return fmt.Sprintf("map with %d keys", len(v))
	default:
		return fmt.Sprintf("unknown type: %T", v)
	}
}

// Type switch with multiple types per case
func TypeSwitchMulti(i interface{}) string {
	switch i.(type) {
	case int, int8, int16, int32, int64:
		return "signed integer"
	case uint, uint8, uint16, uint32, uint64:
		return "unsigned integer"
	case float32, float64:
		return "float"
	case string, []byte:
		return "string-like"
	default:
		return "other"
	}
}

// ============================================================================
// FUNCTION LITERAL (CLOSURE) PATTERNS
// ============================================================================

// Immediately invoked function expression (IIFE)
func IIFE() int {
	return func(x int) int {
		return x * 2
	}(21)
}

// Closure returning closure
func ClosureFactory(multiplier int) func(int) int {
	return func(x int) int {
		return x * multiplier
	}
}

// Recursive closure (must declare variable first)
func RecursiveClosure(n int) int {
	var factorial func(int) int
	factorial = func(n int) int {
		if n <= 1 {
			return 1
		}
		return n * factorial(n-1)
	}
	return factorial(n)
}

// ============================================================================
// STRUCT LITERAL PATTERNS
// ============================================================================

type Point struct {
	X, Y int
}

type Circle struct {
	Center Point
	Radius float64
}

// Nested struct literals
func NestedStructLiteral() Circle {
	return Circle{
		Center: Point{X: 10, Y: 20},
		Radius: 5.0,
	}
}

// Anonymous struct
func AnonymousStruct() {
	person := struct {
		Name string
		Age  int
	}{
		Name: "Alice",
		Age:  30,
	}
	fmt.Println(person)
}

// Struct with embedded anonymous field
type Config struct {
	struct {
		Host string
		Port int
	}
	Timeout time.Duration
}

// ============================================================================
// MAP PATTERNS
// ============================================================================

// Map with function values
var handlers = map[string]func(int) int{
	"double": func(x int) int { return x * 2 },
	"triple": func(x int) int { return x * 3 },
	"square": func(x int) int { return x * x },
}

// Map with struct keys (must be comparable)
type CacheKey struct {
	Path   string
	Method string
}

var cache = map[CacheKey][]byte{}

// Nested maps
var nestedMap = map[string]map[string]int{
	"outer1": {"inner1": 1, "inner2": 2},
	"outer2": {"inner3": 3, "inner4": 4},
}

// ============================================================================
// SLICE PATTERNS
// ============================================================================

// Slice tricks
func SlicePatterns() {
	s := []int{1, 2, 3, 4, 5}

	// Copy slice
	s2 := append([]int(nil), s...)

	// Delete element at index 2
	s3 := append(s[:2], s[3:]...)

	// Insert at index 2
	s4 := append(s[:2], append([]int{99}, s[2:]...)...)

	// Reverse
	for i, j := 0, len(s)-1; i < j; i, j = i+1, j-1 {
		s[i], s[j] = s[j], s[i]
	}

	fmt.Println(s2, s3, s4, s)
}

// Three-index slice (capacity control)
func ThreeIndexSlice() {
	s := []int{1, 2, 3, 4, 5}

	// s[low:high:max] - capacity is max-low
	s2 := s[1:3:4] // len=2, cap=3
	fmt.Println(len(s2), cap(s2))
}
