


# @login_required
# def register_event(request, event_id):
#     """
#     Event registration with advanced retry mechanism to handle database locks
    
#     Args:
#         request: HTTP request
#         event_id: ID of the event to register for
    
#     Returns:
#         JsonResponse with registration status and details
#     """
#     if request.method != 'POST':
#         return JsonResponse({
#             'success': False, 
#             'error': 'Method not allowed. Use POST.',
#             'status_code': 'METHOD_NOT_ALLOWED'
#         }, status=405)
    
#     # Configuration for retry mechanism
#     MAX_RETRIES = 3
#     BASE_WAIT_TIME = 0.5  # Base wait time in seconds
    
#     # Prepare logging context
#     logger.info(f"Registration attempt for event {event_id} by user {request.user.id}")
    
#     for attempt in range(MAX_RETRIES):
#         try:
#             # Exponential backoff for retry attempts
#             wait_time = BASE_WAIT_TIME * (2 ** attempt)
            
#             with transaction.atomic():
#                 try:
#                     # Use select_for_update with timeout to prevent long-running locks
#                     event = Event.objects.select_for_update(
#                         of=('self',),  # Lock only this specific event
#                         skip_locked=True  # Skip if locked by another transaction
#                     ).get(id=event_id)
#                 except DatabaseError as db_err:
#                     # Log the specific database error
#                     logger.warning(f"Database lock attempt {attempt + 1} failed: {db_err}")
                    
#                     # If not the last attempt, wait and retry
#                     if attempt < MAX_RETRIES - 1:
#                         time.sleep(wait_time)
#                         continue
#                     else:
#                         return JsonResponse({
#                             'success': False,
#                             'error': 'Event registration temporarily unavailable. Please try again later.',
#                             'status_code': 'REGISTRATION_LOCKED',
#                             'retry_after': wait_time
#                         }, status=409)
                
#                 # Retrieve user profile
#                 try:
#                     user_profile = request.user.profile
#                 except Profile.DoesNotExist:
#                     return JsonResponse({
#                         'success': False,
#                         'error': 'User profile not found',
#                         'status_code': 'PROFILE_NOT_FOUND'
#                     }, status=400)
                
#                 # Check registration eligibility
#                 can_register, status_message = event.can_register(user_profile)
#                 if not can_register:
#                     return JsonResponse({
#                         'success': False,
#                         'error': status_message,
#                         'status_code': 'REGISTRATION_NOT_ALLOWED'
#                     }, status=400)
                
#                 # Prepare registration data
#                 registration_data = {
#                     'name': request.POST.get('name'),
#                     'email': request.POST.get('email'),
#                 }
                
#                 # Validate registration form
#                 form = EventRegistrationForm(
#                     request.POST, 
#                     event=event, 
#                     user=request.user
#                 )
                
#                 if not form.is_valid():
#                     return JsonResponse({
#                         'success': False,
#                         'errors': form.errors,
#                         'status_code': 'FORM_VALIDATION_ERROR'
#                     }, status=400)
                
#                 # Attempt registration
#                 try:
#                     registration, status = event.register_for_event(
#                         user_profile, 
#                         registration_data
#                     )
                    
#                     # Prepare successful response
#                     response_data = {
#                         'success': True,
#                         'status': status,
#                         'message': (
#                             'Successfully registered' if status == 'registered' 
#                             else 'Added to waitlist'
#                         ),
#                         'waitlist_position': registration.waitlist_position if status == 'waitlist' else None,
#                         'spots_left': event.spots_left,
#                         'registration_id': registration.id,
#                         'retry_attempts': attempt
#                     }
                    
#                     return JsonResponse(response_data)
                
#                 except ValidationError as ve:
#                     return JsonResponse({
#                         'success': False,
#                         'error': str(ve),
#                         'status_code': 'VALIDATION_ERROR'
#                     }, status=400)
                
#                 except Exception as registration_error:
#                     logger.error(f"Registration failed: {registration_error}", exc_info=True)
#                     return JsonResponse({
#                         'success': False,
#                         'error': 'Unexpected registration error',
#                         'status_code': 'UNEXPECTED_REGISTRATION_ERROR'
#                     }, status=500)
        
#         except Event.DoesNotExist:
#             logger.warning(f"Attempted registration for non-existent event {event_id}")
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Event not found',
#                 'status_code': 'EVENT_NOT_FOUND'
#             }, status=404)
        
#         except Exception as unexpected_error:
#             # Catch-all for any unexpected errors
#             logger.error(f"Unexpected error during registration: {unexpected_error}", exc_info=True)
            
#             # If not the last attempt, wait and retry
#             if attempt < MAX_RETRIES - 1:
#                 time.sleep(wait_time)
#                 continue
#             else:
#                 return JsonResponse({
#                     'success': False,
#                     'error': 'An unexpected error occurred',
#                     'status_code': 'SYSTEM_ERROR'
#                 }, status=500)