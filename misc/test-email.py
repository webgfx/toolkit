import win32com.client as win32
outlook = win32.Dispatch('outlook.application')
mail = outlook.CreateItem(0)
mail.To = 'ygu@microsoft.com'
mail.Subject = 'Test'
mail.Body = 'Message body'
mail.HTMLBody = '<h2>HTML Message body</h2>' #this field is optional
mail.Send()
