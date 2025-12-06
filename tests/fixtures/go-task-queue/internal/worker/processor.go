package worker

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/example/task-queue/internal/queue"
)

// Processor is a single-worker task processor for simpler use cases
type Processor struct {
	queue    queue.Queue
	handlers map[string]ProcessFunc
	mu       sync.RWMutex
	ctx      context.Context
	cancel   context.CancelFunc
	running  bool
	wg       sync.WaitGroup
}

// ProcessFunc is a function that processes a task
type ProcessFunc func(ctx context.Context, task *queue.Task) error

// NewProcessor creates a new task processor
func NewProcessor(q queue.Queue) *Processor {
	ctx, cancel := context.WithCancel(context.Background())
	return &Processor{
		queue:    q,
		handlers: make(map[string]ProcessFunc),
		ctx:      ctx,
		cancel:   cancel,
	}
}

// Register registers a handler for a task type
func (p *Processor) Register(taskType string, fn ProcessFunc) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.handlers[taskType] = fn
}

// Start starts processing tasks
func (p *Processor) Start() error {
	p.mu.Lock()
	if p.running {
		p.mu.Unlock()
		return fmt.Errorf("processor already running")
	}
	p.running = true
	p.mu.Unlock()

	p.wg.Add(1)
	go p.loop()

	return nil
}

// loop is the main processing loop
func (p *Processor) loop() {
	defer p.wg.Done()

	for {
		select {
		case <-p.ctx.Done():
			return
		default:
		}

		task, err := p.queue.Dequeue(p.ctx)
		if err != nil {
			if err == queue.ErrQueueEmpty {
				time.Sleep(100 * time.Millisecond)
				continue
			}
			if p.ctx.Err() != nil {
				return
			}
			continue
		}

		p.process(task)
	}
}

// process handles a single task
func (p *Processor) process(task *queue.Task) {
	p.mu.RLock()
	handler, ok := p.handlers[task.Type]
	p.mu.RUnlock()

	if !ok {
		task.State = queue.StateFailed
		task.Error = fmt.Sprintf("no handler for task type: %s", task.Type)
		p.queue.Update(p.ctx, task)
		return
	}

	// Execute handler with panic recovery
	func() {
		defer func() {
			if r := recover(); r != nil {
				task.State = queue.StateFailed
				task.Error = fmt.Sprintf("handler panic: %v", r)
				p.queue.Update(p.ctx, task)
			}
		}()

		if err := handler(p.ctx, task); err != nil {
			task.State = queue.StateFailed
			task.Error = err.Error()
		} else {
			task.State = queue.StateCompleted
		}
		now := time.Now()
		task.CompletedAt = &now
		p.queue.Update(p.ctx, task)
	}()
}

// Stop stops the processor
func (p *Processor) Stop() {
	p.cancel()
	p.wg.Wait()
	p.mu.Lock()
	p.running = false
	p.mu.Unlock()
}

// BatchProcessor processes tasks in batches
type BatchProcessor struct {
	queue     queue.Queue
	batchSize int
	interval  time.Duration
	handler   BatchProcessFunc
	ctx       context.Context
	cancel    context.CancelFunc
	wg        sync.WaitGroup
}

// BatchProcessFunc processes a batch of tasks
type BatchProcessFunc func(ctx context.Context, tasks []*queue.Task) []error

// NewBatchProcessor creates a batch processor
func NewBatchProcessor(q queue.Queue, batchSize int, interval time.Duration, handler BatchProcessFunc) *BatchProcessor {
	ctx, cancel := context.WithCancel(context.Background())
	return &BatchProcessor{
		queue:     q,
		batchSize: batchSize,
		interval:  interval,
		handler:   handler,
		ctx:       ctx,
		cancel:    cancel,
	}
}

// Start starts batch processing
func (bp *BatchProcessor) Start() {
	bp.wg.Add(1)
	go bp.loop()
}

// loop is the batch processing loop
func (bp *BatchProcessor) loop() {
	defer bp.wg.Done()

	ticker := time.NewTicker(bp.interval)
	defer ticker.Stop()

	for {
		select {
		case <-bp.ctx.Done():
			return
		case <-ticker.C:
			bp.processBatch()
		}
	}
}

// processBatch collects and processes a batch
func (bp *BatchProcessor) processBatch() {
	batch := make([]*queue.Task, 0, bp.batchSize)

	// Collect batch
	for i := 0; i < bp.batchSize; i++ {
		task, err := bp.queue.Dequeue(bp.ctx)
		if err != nil {
			break
		}
		batch = append(batch, task)
	}

	if len(batch) == 0 {
		return
	}

	// Process batch
	errs := bp.handler(bp.ctx, batch)

	// Update task states
	for i, task := range batch {
		now := time.Now()
		task.CompletedAt = &now

		if i < len(errs) && errs[i] != nil {
			task.State = queue.StateFailed
			task.Error = errs[i].Error()
		} else {
			task.State = queue.StateCompleted
		}

		bp.queue.Update(bp.ctx, task)
	}
}

// Stop stops batch processing
func (bp *BatchProcessor) Stop() {
	bp.cancel()
	bp.wg.Wait()
}

// FanOutProcessor distributes tasks to multiple handlers in parallel
type FanOutProcessor struct {
	queue    queue.Queue
	handlers []ProcessFunc
	ctx      context.Context
	cancel   context.CancelFunc
	wg       sync.WaitGroup
}

// NewFanOutProcessor creates a fan-out processor
func NewFanOutProcessor(q queue.Queue, handlers ...ProcessFunc) *FanOutProcessor {
	ctx, cancel := context.WithCancel(context.Background())
	return &FanOutProcessor{
		queue:    q,
		handlers: handlers,
		ctx:      ctx,
		cancel:   cancel,
	}
}

// Start starts fan-out processing
func (fp *FanOutProcessor) Start() {
	fp.wg.Add(1)
	go fp.loop()
}

// loop is the main processing loop
func (fp *FanOutProcessor) loop() {
	defer fp.wg.Done()

	for {
		select {
		case <-fp.ctx.Done():
			return
		default:
		}

		task, err := fp.queue.Dequeue(fp.ctx)
		if err != nil {
			if err == queue.ErrQueueEmpty {
				time.Sleep(100 * time.Millisecond)
				continue
			}
			continue
		}

		fp.fanOut(task)
	}
}

// fanOut processes task with all handlers in parallel
func (fp *FanOutProcessor) fanOut(task *queue.Task) {
	var wg sync.WaitGroup
	errs := make([]error, len(fp.handlers))

	for i, handler := range fp.handlers {
		wg.Add(1)
		go func(idx int, h ProcessFunc) {
			defer wg.Done()
			errs[idx] = h(fp.ctx, task)
		}(i, handler)
	}

	wg.Wait()

	// Aggregate errors
	var hasError bool
	var errMsg string
	for _, err := range errs {
		if err != nil {
			hasError = true
			errMsg += err.Error() + "; "
		}
	}

	now := time.Now()
	task.CompletedAt = &now

	if hasError {
		task.State = queue.StateFailed
		task.Error = errMsg
	} else {
		task.State = queue.StateCompleted
	}

	fp.queue.Update(fp.ctx, task)
}

// Stop stops fan-out processing
func (fp *FanOutProcessor) Stop() {
	fp.cancel()
	fp.wg.Wait()
}

// PipelineStage is a stage in a processing pipeline
type PipelineStage struct {
	Name    string
	Handler func(context.Context, *queue.Task) (*queue.Task, error)
}

// Pipeline processes tasks through sequential stages
type Pipeline struct {
	stages []PipelineStage
	queue  queue.Queue
	ctx    context.Context
	cancel context.CancelFunc
	wg     sync.WaitGroup
}

// NewPipeline creates a processing pipeline
func NewPipeline(q queue.Queue, stages ...PipelineStage) *Pipeline {
	ctx, cancel := context.WithCancel(context.Background())
	return &Pipeline{
		stages: stages,
		queue:  q,
		ctx:    ctx,
		cancel: cancel,
	}
}

// AddStage adds a stage to the pipeline
func (p *Pipeline) AddStage(name string, handler func(context.Context, *queue.Task) (*queue.Task, error)) {
	p.stages = append(p.stages, PipelineStage{
		Name:    name,
		Handler: handler,
	})
}

// Start starts the pipeline
func (p *Pipeline) Start() {
	p.wg.Add(1)
	go p.loop()
}

// loop is the pipeline processing loop
func (p *Pipeline) loop() {
	defer p.wg.Done()

	for {
		select {
		case <-p.ctx.Done():
			return
		default:
		}

		task, err := p.queue.Dequeue(p.ctx)
		if err != nil {
			if err == queue.ErrQueueEmpty {
				time.Sleep(100 * time.Millisecond)
				continue
			}
			continue
		}

		p.processPipeline(task)
	}
}

// processPipeline runs task through all stages
func (p *Pipeline) processPipeline(task *queue.Task) {
	current := task

	for _, stage := range p.stages {
		result, err := stage.Handler(p.ctx, current)
		if err != nil {
			now := time.Now()
			task.State = queue.StateFailed
			task.Error = fmt.Sprintf("stage %s failed: %v", stage.Name, err)
			task.CompletedAt = &now
			p.queue.Update(p.ctx, task)
			return
		}
		current = result
	}

	now := time.Now()
	task.State = queue.StateCompleted
	task.CompletedAt = &now
	task.Result = current.Payload
	p.queue.Update(p.ctx, task)
}

// Stop stops the pipeline
func (p *Pipeline) Stop() {
	p.cancel()
	p.wg.Wait()
}
