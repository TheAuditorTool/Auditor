//! Async runtime utilities
//!
//! This module tests extraction of:
//! - async functions
//! - await points
//! - async trait methods
//! - futures and polling

use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll, Waker};
use std::time::{Duration, Instant};
use std::sync::{Arc, Mutex};
use std::collections::VecDeque;

// ============================================================================
// ASYNC FUNCTIONS - Tests rust_async_functions extraction
// ============================================================================

/// Simple async sleep (poll-based)
pub async fn async_sleep(duration: Duration) {
    let start = Instant::now();
    loop {
        if start.elapsed() >= duration {
            return;
        }
        // Yield to scheduler
        yield_now().await;
    }
}

/// Yield execution to allow other tasks to run
pub async fn yield_now() {
    YieldNow(false).await
}

struct YieldNow(bool);

impl Future for YieldNow {
    type Output = ();

    fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> {
        if self.0 {
            Poll::Ready(())
        } else {
            self.0 = true;
            cx.waker().wake_by_ref();
            Poll::Pending
        }
    }
}

/// Async function with return value
pub async fn async_compute(x: i32, y: i32) -> i32 {
    yield_now().await;
    let sum = x + y;
    yield_now().await;
    sum * 2
}

/// Async function that can fail
pub async fn async_fallible(should_fail: bool) -> Result<String, &'static str> {
    yield_now().await;

    if should_fail {
        Err("intentional failure")
    } else {
        Ok("success".to_string())
    }
}

/// Async function with multiple await points
pub async fn async_multi_step(steps: u32) -> Vec<u32> {
    let mut results = Vec::new();

    for i in 0..steps {
        yield_now().await;
        results.push(i * i);
        yield_now().await;
    }

    results
}

/// Async function calling other async functions
pub async fn async_composed() -> i32 {
    let a = async_compute(1, 2).await;
    let b = async_compute(3, 4).await;
    let c = async_compute(a, b).await;
    c
}

/// Async function with early return
pub async fn async_early_return(condition: bool) -> Option<i32> {
    yield_now().await;

    if condition {
        return Some(42);
    }

    yield_now().await;
    yield_now().await;

    None
}

/// Async function with loop and break
pub async fn async_loop_break(limit: u32) -> u32 {
    let mut count = 0;

    loop {
        yield_now().await;
        count += 1;

        if count >= limit {
            break;
        }
    }

    count
}

// ============================================================================
// ASYNC BLOCKS - Inline async expressions
// ============================================================================

/// Returns an async block
pub fn returns_async_block() -> impl Future<Output = i32> {
    async {
        yield_now().await;
        42
    }
}

/// Async block with capture
pub fn async_with_capture(val: i32) -> impl Future<Output = i32> {
    async move {
        yield_now().await;
        val * 2
    }
}

/// Multiple async blocks
pub fn multiple_async_blocks(choice: bool) -> impl Future<Output = &'static str> {
    if choice {
        async {
            yield_now().await;
            "choice a"
        }
    } else {
        async {
            yield_now().await;
            "choice b"
        }
    }
}

// ============================================================================
// CUSTOM FUTURE TYPES - Manual Future implementation
// ============================================================================

/// A future that completes after N polls
pub struct PollCounter {
    remaining: u32,
}

impl PollCounter {
    pub fn new(count: u32) -> Self {
        Self { remaining: count }
    }
}

impl Future for PollCounter {
    type Output = u32;

    fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
        if self.remaining == 0 {
            Poll::Ready(0)
        } else {
            self.remaining -= 1;
            cx.waker().wake_by_ref();
            Poll::Pending
        }
    }
}

/// A future that resolves immediately
pub struct Ready<T>(Option<T>);

impl<T> Ready<T> {
    pub fn new(value: T) -> Self {
        Self(Some(value))
    }
}

impl<T> Future for Ready<T> {
    type Output = T;

    fn poll(mut self: Pin<&mut Self>, _cx: &mut Context<'_>) -> Poll<Self::Output> {
        match self.0.take() {
            Some(v) => Poll::Ready(v),
            None => panic!("Ready polled after completion"),
        }
    }
}

/// A future that never completes
pub struct Pending<T>(std::marker::PhantomData<T>);

impl<T> Pending<T> {
    pub fn new() -> Self {
        Self(std::marker::PhantomData)
    }
}

impl<T> Default for Pending<T> {
    fn default() -> Self {
        Self::new()
    }
}

impl<T> Future for Pending<T> {
    type Output = T;

    fn poll(self: Pin<&mut Self>, _cx: &mut Context<'_>) -> Poll<Self::Output> {
        Poll::Pending
    }
}

// ============================================================================
// ASYNC STREAMS - Iterator-like async pattern
// ============================================================================

/// Async stream trait (simplified)
pub trait AsyncStream {
    type Item;

    fn poll_next(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>>;
}

/// Stream that yields numbers
pub struct CountStream {
    current: u32,
    max: u32,
}

impl CountStream {
    pub fn new(max: u32) -> Self {
        Self { current: 0, max }
    }
}

impl AsyncStream for CountStream {
    type Item = u32;

    fn poll_next(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        if self.current >= self.max {
            Poll::Ready(None)
        } else {
            let val = self.current;
            self.current += 1;
            cx.waker().wake_by_ref();
            Poll::Ready(Some(val))
        }
    }
}

// ============================================================================
// ASYNC CHANNEL - Communication between async tasks
// ============================================================================

/// Simple async channel (unbounded)
pub struct AsyncChannel<T> {
    inner: Arc<Mutex<ChannelInner<T>>>,
}

struct ChannelInner<T> {
    queue: VecDeque<T>,
    wakers: Vec<Waker>,
    closed: bool,
}

impl<T> AsyncChannel<T> {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(Mutex::new(ChannelInner {
                queue: VecDeque::new(),
                wakers: Vec::new(),
                closed: false,
            })),
        }
    }

    /// Create a sender/receiver pair
    pub fn split(&self) -> (Sender<T>, Receiver<T>) {
        (
            Sender { inner: self.inner.clone() },
            Receiver { inner: self.inner.clone() },
        )
    }
}

impl<T> Default for AsyncChannel<T> {
    fn default() -> Self {
        Self::new()
    }
}

/// Sending half of channel
pub struct Sender<T> {
    inner: Arc<Mutex<ChannelInner<T>>>,
}

impl<T> Sender<T> {
    /// Send a value (sync - always succeeds unless closed)
    pub fn send(&self, value: T) -> Result<(), T> {
        let mut inner = self.inner.lock().unwrap();
        if inner.closed {
            return Err(value);
        }
        inner.queue.push_back(value);
        // Wake all waiting receivers
        for waker in inner.wakers.drain(..) {
            waker.wake();
        }
        Ok(())
    }

    /// Close the channel
    pub fn close(&self) {
        let mut inner = self.inner.lock().unwrap();
        inner.closed = true;
        for waker in inner.wakers.drain(..) {
            waker.wake();
        }
    }
}

impl<T> Clone for Sender<T> {
    fn clone(&self) -> Self {
        Self { inner: self.inner.clone() }
    }
}

/// Receiving half of channel
pub struct Receiver<T> {
    inner: Arc<Mutex<ChannelInner<T>>>,
}

impl<T> Receiver<T> {
    /// Receive a value asynchronously
    pub async fn recv(&self) -> Option<T> {
        RecvFuture { inner: self.inner.clone() }.await
    }
}

struct RecvFuture<T> {
    inner: Arc<Mutex<ChannelInner<T>>>,
}

impl<T> Future for RecvFuture<T> {
    type Output = Option<T>;

    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
        let mut inner = self.inner.lock().unwrap();

        if let Some(value) = inner.queue.pop_front() {
            return Poll::Ready(Some(value));
        }

        if inner.closed {
            return Poll::Ready(None);
        }

        inner.wakers.push(cx.waker().clone());
        Poll::Pending
    }
}

// ============================================================================
// ASYNC TASK SPAWNING (conceptual - no real runtime)
// ============================================================================

/// Represents a spawned async task
pub struct Task<T> {
    future: Pin<Box<dyn Future<Output = T> + Send>>,
}

impl<T> Task<T> {
    /// Create a new task from a future
    pub fn spawn<F>(future: F) -> Self
    where
        F: Future<Output = T> + Send + 'static,
    {
        Self {
            future: Box::pin(future),
        }
    }

    /// Poll the task once
    pub fn poll(&mut self, cx: &mut Context<'_>) -> Poll<T> {
        self.future.as_mut().poll(cx)
    }
}

/// Simple task queue for demonstration
pub struct TaskQueue {
    tasks: Vec<Task<()>>,
}

impl TaskQueue {
    pub fn new() -> Self {
        Self { tasks: Vec::new() }
    }

    pub fn spawn<F>(&mut self, future: F)
    where
        F: Future<Output = ()> + Send + 'static,
    {
        self.tasks.push(Task::spawn(future));
    }

    pub fn len(&self) -> usize {
        self.tasks.len()
    }

    pub fn is_empty(&self) -> bool {
        self.tasks.is_empty()
    }
}

impl Default for TaskQueue {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// ASYNC COMBINATORS
// ============================================================================

/// Join two futures, running both to completion
pub async fn join<A, B, T, U>(a: A, b: B) -> (T, U)
where
    A: Future<Output = T>,
    B: Future<Output = U>,
{
    // Simplified - real impl would poll both concurrently
    let result_a = a.await;
    let result_b = b.await;
    (result_a, result_b)
}

/// Select first completing future
pub async fn race<A, B, T>(a: A, b: B) -> T
where
    A: Future<Output = T>,
    B: Future<Output = T>,
{
    // Simplified - real impl would poll both and return first ready
    a.await
}

/// Map a future's output
pub async fn map<F, T, U, M>(future: F, mapper: M) -> U
where
    F: Future<Output = T>,
    M: FnOnce(T) -> U,
{
    let result = future.await;
    mapper(result)
}

/// Chain two futures
pub async fn then<F1, F2, T, U>(first: F1, next: impl FnOnce(T) -> F2) -> U
where
    F1: Future<Output = T>,
    F2: Future<Output = U>,
{
    let result = first.await;
    next(result).await
}

#[cfg(test)]
mod tests {
    use super::*;

    // Helper to run a future to completion (single-threaded)
    fn block_on<F: Future>(mut future: F) -> F::Output {
        use std::task::{RawWaker, RawWakerVTable};

        fn dummy_waker() -> Waker {
            fn clone(_: *const ()) -> RawWaker { RawWaker::new(std::ptr::null(), &VTABLE) }
            fn wake(_: *const ()) {}
            fn wake_by_ref(_: *const ()) {}
            fn drop(_: *const ()) {}

            static VTABLE: RawWakerVTable = RawWakerVTable::new(clone, wake, wake_by_ref, drop);

            unsafe { Waker::from_raw(RawWaker::new(std::ptr::null(), &VTABLE)) }
        }

        let waker = dummy_waker();
        let mut cx = Context::from_waker(&waker);
        let mut future = unsafe { Pin::new_unchecked(&mut future) };

        loop {
            match future.as_mut().poll(&mut cx) {
                Poll::Ready(result) => return result,
                Poll::Pending => {}
            }
        }
    }

    #[test]
    fn test_async_compute() {
        let result = block_on(async_compute(2, 3));
        assert_eq!(result, 10); // (2+3)*2 = 10
    }

    #[test]
    fn test_async_multi_step() {
        let result = block_on(async_multi_step(4));
        assert_eq!(result, vec![0, 1, 4, 9]);
    }

    #[test]
    fn test_async_composed() {
        let result = block_on(async_composed());
        // async_compute(1,2) = 6
        // async_compute(3,4) = 14
        // async_compute(6,14) = 40
        assert_eq!(result, 40);
    }

    #[test]
    fn test_poll_counter() {
        let result = block_on(PollCounter::new(5));
        assert_eq!(result, 0);
    }

    #[test]
    fn test_ready_future() {
        let result = block_on(Ready::new(42));
        assert_eq!(result, 42);
    }

    #[test]
    fn test_channel() {
        let channel = AsyncChannel::new();
        let (tx, rx) = channel.split();

        tx.send(1).unwrap();
        tx.send(2).unwrap();
        tx.send(3).unwrap();
        tx.close();

        let result = block_on(async {
            let mut values = Vec::new();
            while let Some(v) = rx.recv().await {
                values.push(v);
            }
            values
        });

        assert_eq!(result, vec![1, 2, 3]);
    }
}
